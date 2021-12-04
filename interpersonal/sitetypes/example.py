"""Sites hosted on Github"""

import hashlib
import os.path
import re
import textwrap
import typing

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from interpersonal.errors import InterpersonalNotFoundError
from interpersonal.sitetypes import base
from interpersonal.util import extension_from_content_type


_example_repo_posts = {
    "/blog/post-one": textwrap.dedent(
        """\
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
        """\
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


class HugoExampleBlog(base.HugoBase):
    """An example blog that looks like a Hugo blog to Interpersonal.

    Useful for testing and maybe nothing else.

    Includes a couple of example posts.

    Class properties:

    posts:              A dictionary of posts.
                        The key is the post slug, and the value is raw post content.
    media:              Media storage if collectmedia=False,
                        or the media staging area if collectmedia=True.
                        The key is the media hash,
                        and the value is a werkzeug.FileStorage object.
    collectedmedia:     Permanent media storage if collectmedia=True, otherwise unused.
                        The key is the post URI, and the value is a sub-dict,
                        where the sub-key is the media hash,
                        and the sub-value is a werkzeug.FileStorage object.
    """

    def __init__(self, name, uri, slugprefix, mediaprefix, collectmedia=False):
        self.posts: typing.Dict[str, str] = _example_repo_posts
        self.media: typing.Dict[str, FileStorage] = {}
        self.collectedmedia: typing.Dict[str, FileStorage] = {}
        super().__init__(name, uri, slugprefix, mediaprefix, collectmedia=collectmedia)

    def _get_raw_post_body(self, uri: str) -> str:
        path = re.sub(re.escape(self.baseuri), "", uri)
        if not path.startswith("/"):
            path = f"/{path}"
        return self.posts[path]

    def _add_raw_post_body(self, slug: str, raw_body: str) -> str:
        ppath = self._post_path(slug)
        self.posts[f"/{ppath}"] = raw_body
        return f"{self.baseuri}{ppath}"

    def _add_media(self, media: typing.List[FileStorage]) -> typing.List[str]:
        uris = []
        for item in media:
            uri = self._media_item_uri(item)
            self.media[uri] = item
            uris.append(uri)
        return uris

    def _collect_media_for_post(
        self, postslug: str, postbody: str, media: typing.List[str]
    ):
        # TODO: update the post body with the new image URIs
        if postslug not in self.collectedmedia:
            self.collectedmedia[postslug] = {}
        for uri in media:

            if uri not in self.media:
                raise InterpersonalNotFoundError(
                    f"Media item from URI {uri} has not been saved"
                )
            item = self.media[uri]
            self.collectedmedia[postslug][uri] = item
