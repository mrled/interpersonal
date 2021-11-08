"""Sites hosted on Github"""

from ghapi.all import GhApi

from interpersonal.sitetypes import base


class HugoGithubRepo(base.HugoBase):
    """A Hugo blog kept in a github.com repo

    Assumptions:
    - The blog is hosted on the default branch
    """

    def __init__(self, name, uri, owner: str, repo: str, token: str):
        self.owner = owner
        self.repo = repo
        self.api = GhApi(owner=owner, repo=repo, token=token)
        super().__init__(name, uri)

    def _get_raw_post_body(self, uri: str) -> base.HugoPostSource:
        return self.api(
            r"/repos/{owner}/{repo}/contents/{path}",
            "GET",
            route=dict(owner=self.owner, repo=self.repo, path=self._uri2indexmd(uri)),
        )
