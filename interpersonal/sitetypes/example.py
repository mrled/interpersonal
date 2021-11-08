"""Sites hosted on Github"""

import re
import textwrap

from interpersonal.sitetypes import base


_example_repo_posts = {
    "/blog/post-one": textwrap.dedent(
        """
        ---
        title: Post one
        date: 2021-01-27
        tags:
        - billbert
        - bobson
        ---
        Here's some example text from the indieweb.org wiki:

        This technique has the advantage of ensuring that each object that is created has its own URL (each piece of data has its own link). This also gives the server an opportunity to handle each entity separately. E.g., rather than creating a duplicate of an existing venue, it may give back a link to one that was already created, possibly even merging in newly received data first.
        """
    ),
    "/blog/post-two": textwrap.dedent(
        """
        ---
        title: Post two
        date: 2021-02-14
        tags:
        - bobson
        - tomerton
        ---
        Please find below a paragraph from the micropub spec:

        If there was an error with the request, the endpoint MUST return an appropriate HTTP status code, typically 400, 401, or 403, and MAY include a description of the error. If an error body is returned, the response body MUST be encoded as a [JSON] object and include at least a single property named error. The following error codes are defined.
        """
    ),
}


class HugoExampleRepo(base.HugoBase):
    """A Hugo blog kept in a github.com repo

    Assumptions:
    - The blog is hosted on the default branch
    """

    def __init__(self, name, uri):
        self.posts = _example_repo_posts
        super().__init__(name, uri)

    def _get_raw_post_body(self, uri: str) -> base.HugoPostSource:
        path = re.sub(re.escape(self.uri), "", uri)
        return self.posts[path]