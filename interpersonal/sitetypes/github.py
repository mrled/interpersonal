"""Sites hosted on Github"""

import base64
import json

from interpersonal.sitetypes import base

from flask import current_app
from ghapi.all import GhApi


class HugoGithubRepo(base.HugoBase):
    """A Hugo blog kept in a github.com repo

    Assumptions:
    - The blog is hosted on the default branch
    """

    def __init__(self, name, uri, owner: str, repo: str, token: str):
        self.owner = owner
        self.repo = repo
        self.api = GhApi(token=token)
        super().__init__(name, uri)

    def _logged_api(self, *args, **kwargs):
        """Call self.api, logging parameters and results"""
        try:
            resp = self.api(*args, **kwargs)
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
        if slug.startswith("/"):
            slug = slug[1:]
        self._logged_api(
            r"/repos/{owner}/{repo}/contents/{path}",
            "PUT",
            route=dict(
                owner=self.owner, repo=self.repo, path=f"content/{slug}/index.md"
            ),
            data={
                "message": f"Creating post for {slug} from Interpersonal",
                "content": base64.b64encode(raw_body.encode()).decode(),
            },
        )
        return f"{self.baseuri}{slug}"
