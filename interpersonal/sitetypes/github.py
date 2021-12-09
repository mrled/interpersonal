"""Sites hosted on Github"""

import base64
import json
import os.path
import re
import time
import typing
from datetime import datetime

import jwt
import requests
from flask import current_app
from ghapi.all import GhApi

from interpersonal.errors import InterpersonalNotFoundError
from interpersonal.sitetypes import base


class GithubAppJwt:
    """A Github JWT token

    <https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps#jwt-payload>

    app_id:                 The Github application ID
    private_key_pem:        A string containing either the private key or a path to it
    """

    def __init__(self, private_key_pem: str, app_id: str):
        self.app_id = app_id
        try:
            with open(private_key_pem) as pkf:
                key_contents = pkf.read().encode()
        except FileNotFoundError:
            key_contents = private_key_pem.encode()
        self.key = key_contents
        self._token = None
        self.expires = 0

    @property
    def token(self):
        """Retrieve the JWT token

        Caches the result and only regenerates the token if it is expiring soon
        """
        expiring_soon = self.expires < (int(time.time()) - 15)
        if self._token is None or expiring_soon:
            now = int(time.time())
            expires = now + (10 * 60)
            payload = {
                # issued at time, 60 seconds in the past to allow for clock drift
                "iat": now - 60,
                # JWT expiration time (10 minute maximum)
                "exp": expires,
                # GitHub App's identifier
                "iss": int(self.app_id),
            }
            self.expires = expires
            token = jwt.encode(payload, self.key, "RS256")
            if isinstance(token, bytes):
                token = token.decode("utf-8")
            self._token = token
        return self._token


class GithubApiAppJwtAuth:
    """Call the Github API with the app JWT bearer token authentication.

    This is for authenticating _as the app_,
    NOT for authenticating _as a particular installation of the app_.
    This is required for URIs like /app/installations,
    which are not specific to a given installation but are for the whole app.

    URIs like "/repos/{owner}/{repo}/contents/{path}" only work when authenticating
    _as a particular installation of the app_.
    These routes should not be called from this function.

    This function uses the requests library to call the GH REST API directly.
    For other API calls, we use the GhApi package,
    but that package has problems with JWT bearer token auth.
    See /docs/ghapi.md for more details.
    """

    def __init__(self, ghajwt: GithubAppJwt):
        self.ghajwt = ghajwt
        self._install_tokens = {}

    def call(self, method, uri, headers=None, **kwargs):
        """Call the Github API with the app JWT bearer token authentication.

        This is for authenticating _as the app_,
        NOT for authenticating _as a particular installation of the app_.
        This is required for URIs like /app/installations,
        which are not specific to a given installation but are for the whole app.

        URIs like "/repos/{owner}/{repo}/contents/{path}" only work when authenticating
        _as a particular installation of the app_.
        These routes should not be called from this function.

        This function uses the requests library to call the GH REST API directly.
        For other API calls, we use the GhApi package,
        but that package has problems with JWT bearer token auth.
        See /docs/ghapi.md for more details.
        """

        # Allow passing in headers=, but always set auth/accept/UA headers here
        override_headers = {
            "Authorization": f"Bearer {self.ghajwt.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "interpersonal.micahrl.com",
        }

        input_headers = headers or {}
        req_headers = {**input_headers, **override_headers}
        result = requests.request(method, uri, headers=req_headers, **kwargs)
        result.raise_for_status()
        return result.json()

    def app_installations(self):
        """Call the GH API for /app/installations

        See example result in
        /docs/github-rest-api-examples/app-installations.json
        """
        result = self.call("GET", f"https://api.github.com/app/installations")
        return result

    def app_installations_instid_accesstoks(self, instid):
        """Call the GH API for /app/installations/:installation_id/access_tokens

        See example result in
        /docs/github-rest-api-examples/app-installations-instid-accesstokens.json
        """
        result = self.call(
            "POST", f"https://api.github.com/app/installations/{instid}/access_tokens"
        )
        return result

    # TODO: list all the different Github authentication types and point to their docs
    #       ... having the JWT tokens to auth the app and then get individual inst tokens is confusing
    def install_token(self, owner: str):
        """Get an access token for modifying repo content.

        owner:          The GH username of the owner of the repo we're installed to.
                        This is probably just your Github username,
                        but if you installed the app into an org,
                        it will be the org name.

        - Get a list of all installations
        - Find our owner's installation ID
        - Get access token for that installation

        Caches the result and only regenerates the token if it is expiring soon
        """
        if (
            owner not in self._install_tokens
            or self._install_tokens[owner]["expires_at"] <= datetime.utcnow()
        ):
            installs = self.app_installations()
            ours = [i for i in installs if i["account"]["login"] == owner]
            if len(ours) > 1:
                raise Exception(
                    "Unexpected API result, multiple installations for our user"
                )
            if len(ours) < 1:
                raise Exception(f"App has not been installed to {owner}'s account")
            install = ours[0]
            tok = self.app_installations_instid_accesstoks(install["id"])

            parsed_expires_at = datetime.strptime(
                tok["expires_at"], "%Y-%m-%dT%H:%M:%SZ"
            )
            tok["expires_at"] = parsed_expires_at

            self._install_tokens[owner] = tok

        return self._install_tokens[owner]


class HugoGithubRepo(base.HugoBase):
    """A Hugo blog kept in a github.com repo

    Assumptions:
    - The blog is hosted on the default branch

    A note on "content" with Github and Hugo:
    -----------------------------------------

    The word "content" is a bit overloaded within these realms.
    Be aware of the following:

    * Hugo uses it for your site's content, so a blog post might be at content/blog/post-slug/index.md. This is the value we referemce with 'self.dirs.content'.
    * Github uses it in several REST API paths, e.g. "/repos/{owner}/{repo}/contents/{path}" to get the _contents_ of a file at {path}
    """

    def __init__(
        self,
        name,
        uri,
        interpersonal_uri,
        slugprefix,
        owner: str,
        repo: str,
        branch: str,
        github_app_id: str,
        private_key_pem: str,
        *,
        mediastaging="",
        mediaprefix="",
    ):
        self.owner = owner
        self.repo = repo
        self.github_app_id = github_app_id
        ghapp_jwt = GithubAppJwt(private_key_pem, github_app_id)
        self.ghappapi = GithubApiAppJwtAuth(ghapp_jwt)
        self.mediadir = f"static/{mediaprefix.strip('/')}"
        self.branch = branch

        super().__init__(
            name,
            uri,
            interpersonal_uri,
            slugprefix,
            mediaprefix=mediaprefix,
            mediastaging=mediastaging,
        )

    def _logged_api(self, *args, **kwargs):
        """Call self.api, logging parameters and results"""

        apptok = self.ghappapi.install_token(self.owner)
        api = GhApi(token=apptok["token"])

        try:
            resp = api(*args, **kwargs)
            current_app.logger.debug(
                f"_logged_api called with *args {args} and **kwargs {kwargs}, returned {resp}"
            )
            return resp
        except BaseException as exc:
            current_app.logger.debug(
                f"_logged_api called with *args {args} and **kwargs {kwargs} threw exception {exc}"
            )

            # GhApi doesn't surface error details from Github
            # Try to find them ourselves here
            # <https://github.com/fastai/ghapi/issues/79>
            try:

                # Reminder: you can only call .read() once, and there is no .seek()
                exc_fp_data = exc.fp.read()

                result_body = json.loads(exc_fp_data)
                current_app.logger.debug(f"Result body from github: {result_body}")
            except BaseException as inner_exc:
                current_app.logger.debug(
                    f"Tried to get result body from Github, but was unsuccessful, err: {inner_exc}"
                )

            raise exc

    def _get_raw_post_body(self, uri: str) -> base.HugoPostSource:
        for indexname in ["index.md", "index.html"]:
            indexpath = os.path.join(self._uri_to_post_bundle_dir(uri), indexname)
            resp = self._get_repo_file_if_exists(indexpath)
            if resp:
                break
        else:
            raise InterpersonalNotFoundError
        content = base64.b64decode(resp["content"]).decode()
        current_app.logger.debug(
            f"_get_raw_post_body({uri}) found b64-decoded file contents of {content}"
        )
        return content

    def _add_raw_post_body(self, slug: str, raw_body: str, body_type: str = "") -> str:
        ppath = self._post_path(slug)
        if body_type == "html":
            filename = "index.html"
        else:
            filename = "index.md"
        self._logged_api(
            r"/repos/{owner}/{repo}/contents/{path}",
            "PUT",
            route=dict(
                owner=self.owner,
                repo=self.repo,
                path=f"{self.dirs.content}/{ppath}/{filename}",
            ),
            data={
                "message": f"Creating post for {slug} from Interpersonal",
                "content": base64.b64encode(raw_body.encode()).decode(),
            },
        )
        return f"{self.baseuri}{ppath}"

    def _get_repo_file_if_exists(self, path: str) -> typing.Union[typing.Any, None]:
        """Retrieve a single file if it exists, or None if not"""
        try:
            get_resp = self._logged_api(
                r"/repos/{owner}/{repo}/contents/{path}",
                "GET",
                route=dict(owner=self.owner, repo=self.repo, path=path),
            )
            current_app.logger.debug(f"Successfully retrieved file from {path}")
            return get_resp

        except BaseException as exc:
            try:
                statuscode = int(exc.status)
            except BaseException as inner_exc:
                statuscode = None
            if statuscode != 404:
                current_app.logger.error(
                    f"Unhandled error trying to talk to github, re-raising..."
                )
                raise
            current_app.logger.debug(f"No file exists at {path}")
            return None

    def _add_repo_file_if_not_exists(
        self, relpath: str, opaque_file: base.OpaqueFile
    ) -> base.AddedMediaItem:
        """Given a repo-relative path and a file, upload it if it does not exist"""
        # TODO: are githubusercontent.com URIs going to work well?
        uploaded_uri = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/content/{relpath}"
        file_exists = self._get_repo_file_if_exists(relpath)
        if file_exists:
            current_app.logger.debug(
                f"Media already exists at {relpath}, nothing to do..."
            )
            created = False
        else:
            current_app.logger.debug(
                f"Media does not yet exist at {relpath}, will upload..."
            )
            put_resp = self._logged_api(
                r"/repos/{owner}/{repo}/contents/{path}",
                "PUT",
                route=dict(owner=self.owner, repo=self.repo, path=relpath),
                data=dict(
                    message=f"Add media item {relpath}",
                    content=base64.b64encode(opaque_file.contents).decode(),
                ),
            )
            created = True

        return base.AddedMediaItem(uploaded_uri, created)

    def _add_media(
        self, media: typing.List[base.OpaqueFile]
    ) -> typing.List[base.AddedMediaItem]:
        items: typing.List[base.AddedMediaItem] = []
        for item in media:
            relpath = f"{self.mediadir}/{item.hexdigest}/{item.filename}"
            if self.mediastaging:
                added = self._add_media_staging([item])
                items += added
            else:
                uploaded = self._add_repo_file_if_not_exists(relpath, item)
                items.append(uploaded)
        return items

    def _delete_media(self, uris: typing.List[str]):
        """Delete media from Github.

        Not required for the implementation, but useful for e2e tests.

        Assumes URIs are raw.githubusercontent.com URIs - NOT final published content URIs!
        Again, this is really just for testing.

        TODO: Modify this to work in remote media dir mode, and make it a noop in local staging mode
            Was originally written assuming that the media endpoint uploads directly to
            a staging directory in the Github repo, and the files are later moved.
            However, now when Interpersonal is in staging mode,
            it holds media files temporarily on its own server,
            so this is only useful in remote media dir mode.
        """
        for uri in uris:
            esc_uri_prefix = re.escape(
                f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/content/"
            )
            relpath = re.sub(esc_uri_prefix, "", uri)

            # Get the file so that we can reference its sha
            get_resp = self._logged_api(
                r"/repos/{owner}/{repo}/contents/{path}",
                "GET",
                route=dict(owner=self.owner, repo=self.repo, path=relpath),
            )

            # Actually delete the file, referencing the file's sha
            del_resp = self._logged_api(
                r"/repos/{owner}/{repo}/contents/{path}",
                "DELETE",
                route=dict(owner=self.owner, repo=self.repo, path=relpath),
                data=dict(
                    message=f"Remove media item {relpath}",
                    sha=get_resp["sha"],
                ),
            )

    def _collect_media_for_post(
        self, postslug: str, postbody: str, media: typing.List[str]
    ) -> str:
        for staging_uri in media:
            if not staging_uri.startswith(self.interpersonal_uri):
                current_app.logger.debug(
                    f"Media collection will skip URI '{staging_uri}' as it is not prefixed with what we expect '{self.interpersonal_uri}'."
                )
                continue
            splituri = staging_uri.split("/")
            digest = splituri[-2]
            filename = splituri[-1]
            localpath = os.path.join(self.mediastaging, digest, filename)
            repopath = os.path.join(
                "content", self.slugprefix, postslug, digest, filename
            )
            if not os.path.exists(localpath):
                raise InterpersonalNotFoundError(localpath)
            new_uri = self._media_item_uri_collected(postslug, staging_uri)
            postbody = re.sub(re.escape(staging_uri), new_uri, postbody)

            repofile = self._get_repo_file_if_exists(repopath)
            if repofile:
                current_app.logger.debug(
                    f"Media already exists at {repopath}, nothing to do..."
                )
                continue
            else:
                current_app.logger.debug(
                    f"Media does not yet exist at {repopath}, will upload..."
                )

            with open(localpath, "rb") as fp:
                b64content = base64.b64encode(fp.read()).decode()

            put_resp = self._logged_api(
                r"/repos/{owner}/{repo}/contents/{path}",
                "PUT",
                route=dict(owner=self.owner, repo=self.repo, path=repopath),
                data=dict(
                    message=f"Add media item {repopath}",
                    content=b64content,
                ),
            )

        return postbody