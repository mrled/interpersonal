"""Sites hosted on Github"""

import base64
import json
import re
import time
import typing
from dataclasses import dataclass
from datetime import datetime

import jwt
import requests
from flask import current_app
from ghapi.all import GhApi
from werkzeug.datastructures import FileStorage
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
        slugprefix,
        mediaprefix,
        owner: str,
        repo: str,
        branch: str,
        github_app_id: str,
        private_key_pem: str,
        collectmedia=None,
    ):
        self.owner = owner
        self.repo = repo
        self.github_app_id = github_app_id
        ghapp_jwt = GithubAppJwt(private_key_pem, github_app_id)
        self.ghappapi = GithubApiAppJwtAuth(ghapp_jwt)
        self.mediadir = f"static/{mediaprefix.strip('/')}"
        self.branch = branch

        super().__init__(name, uri, slugprefix, mediaprefix, collectmedia)

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
                result_body = json.loads(exc.fp.read())
                current_app.logger.debug(f"Result body from github: {result_body}")
            except BaseException as inner_exc:
                current_app.logger.debug(
                    f"Tried to get result body from Github, but was unsuccessful, err: {inner_exc}"
                )

            raise exc

    def _get_raw_post_body(self, uri: str) -> base.HugoPostSource:
        resp = self._logged_api(
            r"/repos/{owner}/{repo}/contents/{path}",
            "GET",
            route=dict(owner=self.owner, repo=self.repo, path=self._uri2indexmd(uri)),
        )
        content = base64.b64decode(resp["content"]).decode()
        current_app.logger.debug(
            f"_get_raw_post_body({uri}) found b64-decoded file contents of {content}"
        )
        return content

    def _add_raw_post_body(self, slug: str, raw_body: str) -> str:
        ppath = self._post_path(slug)
        self._logged_api(
            r"/repos/{owner}/{repo}/contents/{path}",
            "PUT",
            route=dict(
                owner=self.owner,
                repo=self.repo,
                path=f"{self.dirs.content}/{ppath}/index.md",
            ),
            data={
                "message": f"Creating post for {slug} from Interpersonal",
                "content": base64.b64encode(raw_body.encode()).decode(),
            },
        )
        return f"{self.baseuri}{ppath}"

    def _add_media(self, media: typing.List[FileStorage]) -> typing.List[str]:
        uris = []
        for item in media:
            digest = self._media_item_hash(item)
            filename = self._media_item_filename(item)
            relpath = f"{self.mediadir}/{digest}/{filename}"
            resp = self._logged_api(
                r"/repos/{owner}/{repo}/contents/{path}",
                "PUT",
                route=dict(owner=self.owner, repo=self.repo, path=relpath),
                data=dict(
                    message=f"Adding media item {relpath}",
                    content=base64.b64encode(item.read()).decode(),
                ),
            )
            # TODO: are githubusercontent.com URIs going to work well?
            uri = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/content/{relpath}"
            uris.append(uri)
        return uris

    def _collect_media_for_post(
        self, postslug: str, postbody: str, media: typing.List[str]
    ):
        # We expect the media to be raw.githubusercontent.com URIs.
        # do _not_ try to collect media at any other URI
        # TODO: are githubusercontent.com URIs going to work well?
        uri_prefix = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/{self.dirs.content}/"

        relpaths = []

        for uri in media:
            if not uri.startswith(uri_prefix):
                current_app.logger.debug(
                    f"Media collection will skip URI '{uri}' as it is not prefixed with what we expect '{uri_prefix}'."
                )
                continue

            relpathidx = len(uri_prefix) - 1

            # this will be like static/media/<file hash>/<file name>.jpeg
            oldpath = uri[relpathidx:]

            relpaths.append(oldpath)

        if len(relpaths) < 1:
            current_app.logger.debug(f"No URIs to move")
            return

        # Get the branch object
        # We need this to get the sha of the current branch so we can commit to it later.
        branch_resp = self._logged_api(
            r"/repos/{owner}/{repo}/branches/{branch}",
            "GET",
            route=dict(owner=self.owner, repo=self.repo, branch=self.branch),
        )
        current_branch_sha = branch_resp["sha"]

        # Get the tree for the tip of that branch
        # This contains info on all files in the current commit.
        # TODO: this might not work for large repos which will not return the whole tree in one request?
        tree_resp = self._logged_api(
            r"/repos/{owner}/{repo}/git/trees/{sha}",
            "GET",
            route=dict(owner=self.owner, repo=self.repo, sha=current_branch_sha),
        )
        tree_sha = tree_resp["sha"]

        # Create a new tree object.
        # We will use this to move the files from their old location to the new one.
        newtree = {"base_tree": tree_sha, "tree": []}

        # A list of tree children with the OLD data
        tree_children_old = {}

        for child in tree_resp["tree"]:
            if child["path"] in relpaths:
                tree_children_old["path"] = child

        for oldpath in relpaths:
            oldobj = tree_children_old[oldpath]

            # newpath will be like content/blog/<post slug>/<file hash>/<file name>.jpeg
            newpath = re.sub(
                f"{self.dirs.static}/{self.mediadir}",
                f"{self.dirs.content}/{self.slugprefix}/{postslug}",
                oldpath,
            )

            # We move objects by setting their "path" property to a new location,
            # and referencing their "sha" property (the hash of their contents).
            tree_child = {
                "path": newpath,
                "mode": oldobj["mode"],
                "type": oldobj["type"],
                "sha": oldobj["sha"],
            }

            newtree["tree"].append(tree_child)

        # Create a new tree
        newtree_resp = self._logged_api(
            r"/repos/{owner}/{repo}/git/trees?recursive=1",
            "POST",
            route=dict(owner=self.owner, repo=self.repo),
            data=newtree,
        )

        # Create a Git commit containing the new tree with a parent of the current version
        commit_resp = self._logged_api(
            r"/repos/{owner}/{repo}/git/commits",
            "POST",
            route=dict(owner=self.owner, repo=self.repo),
            data={
                "message": f"Renaming {relpaths} to live in the collection for the slug {postslug}",
                "tree": newtree_resp["sha"],
                "parents": [current_branch_sha],
            },
        )

        # Update branch to the new commit
        branch_upd_resp = self._logged_api(
            r"/repos/{owner}/{repo}/git/refs/heads/{branch}",
            "PATCH",
            route=dict(owner=self.owner, repo=self.repo, branch=self.branch),
            data={"sha": commit_resp["sha"]},
        )

        # TODO: Update the post body also!
