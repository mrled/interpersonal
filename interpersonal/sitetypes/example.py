"""Sites hosted on Github"""

import os
import os.path
import re
import textwrap
import typing

from flask import current_app

from interpersonal.errors import InterpersonalNotFoundError
from interpersonal.sitetypes import base


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
    media:              Media storage.
                        TODO: rethink this, now that media can just be stored in staging area?
                        The key is the media URI,
                        and the value is a base.OpaqueFile object.
                        Note that the media URI will be either the staging version
                        (part of Interpersonal, hosted under /microblog/<blog name>/staging)
                        or the mediadir version
                        (part of the blog, hosted under the blog's mediaprefix).
    collectedmedia:     Permanent media storage if mediastaging is set, otherwise unused.
                        The key is the final media URI, and the value a base.OpaqueFile object.
                        Note that the final media URI is hosted on the blog itself
                        somewhere under /<slugprefix>/<post slug>/....

    TODO: Make this an actual webserver so that it can really serve a blog?
    TODO: At least serve media?
    TODO: remove the .media and .collectedmedia members, and just use the filesystem
    """

    def __init__(
        self,
        name,
        uri,
        interpersonal_uri,
        slugprefix,
        *,
        mediaprefix="",
        mediastaging="",
    ):
        self.posts: typing.Dict[str, str] = _example_repo_posts
        self.media: typing.Dict[str, base.OpaqueFile] = {}
        self.collectedmedia: typing.Dict[str, base.OpaqueFile] = {}
        super().__init__(
            name,
            uri,
            interpersonal_uri,
            slugprefix,
            mediaprefix=mediaprefix,
            mediastaging=mediastaging,
        )

    def _get_raw_post_body(self, uri: str) -> str:
        path = re.sub(re.escape(self.baseuri), "", uri)
        if not path.startswith("/"):
            path = f"/{path}"
        return self.posts[path]

    def _add_raw_post_body(self, slug: str, raw_body: str, body_type: str = "") -> str:
        ppath = self._post_path(slug)
        self.posts[f"/{ppath}"] = raw_body
        return f"{self.baseuri}{ppath}"

    def _add_media(
        self, media: typing.List[base.OpaqueFile]
    ) -> typing.List[base.AddedMediaItem]:
        items: typing.List[base.AddedMediaItem] = []
        for item in media:
            if self.mediastaging:
                uri = self._media_item_uri_staging(item)
                media_parent_dir = f"{self.mediastaging}"
            else:
                # TODO: This is broken in Dedicated Media Location Mode
                # ... there will be no self.mediastaging directory
                uri = self._media_item_uri_mediadir(item)
                media_parent_dir = f"{self.mediastaging}/{self.mediaprefix}"
            file_parent_dir = os.path.join(media_parent_dir, item.hexdigest)
            item_path = os.path.join(file_parent_dir, item.filename)
            os.makedirs(file_parent_dir, exist_ok=True)
            if os.path.exists(item_path):
                created = False
            else:
                with open(item_path, "wb") as fp:
                    fp.write(item.contents)
                self.media[uri] = item
                created = True
            items.append(base.AddedMediaItem(uri, created))
        return items

    def _collect_media_for_post(
        self, postslug: str, postbody: str, media: typing.List[str]
    ) -> str:
        for staging_uri in media:

            if not staging_uri.startswith(self.interpersonal_uri):
                current_app.logger.debug(
                    f"Media collection will skip URI '{staging_uri}' as it is not prefixed with what we expect '{self.interpersonal_uri}'."
                )
                continue

            if staging_uri not in self.media:
                raise InterpersonalNotFoundError(
                    f"Media item from URI {staging_uri} has not been saved"
                )

            new_uri = self._media_item_uri_collected(postslug, staging_uri)
            self.collectedmedia[new_uri] = self.media[staging_uri]
            postbody = re.sub(re.escape(staging_uri), new_uri, postbody)

        return postbody
