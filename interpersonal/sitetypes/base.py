"""The base class for Hugo blogs"""

import copy
import os
import re
import typing
from datetime import date, datetime
from werkzeug.datastructures import FileStorage

import yaml
from flask import current_app

from interpersonal.errors import MicropubDuplicatePostError, MicropubInvalidRequestError
from interpersonal.util import CaseInsensitiveDict


def slugify(text: str) -> str:
    """Given some input text, create a URL slug

    Designed to handle a title, or a full post content.
    """
    if not text:
        # Return a date
        return datetime.now().strftime("%Y%m%d-%H%M")
    else:
        lower = text.lower()
        words = lower.split(" ")
        basis = words[0:11]
        rejoined = " ".join(basis)
        no_non_word_chars = re.sub(r"[^\w ]+", "", rejoined)
        no_spaces = re.sub(" +", "-", no_non_word_chars)
        return no_spaces


def normalize_baseuri(baseuri: str) -> str:
    """Normalize a baseuri

    If it doesn't end in a slash, add one.
    """
    if baseuri[-1] != "/":
        return baseuri + "/"
    return baseuri


class HugoPostSource:
    def __init__(self, frontmatter: dict, content: str):
        self.frontmatter = frontmatter
        self.content = content

    @classmethod
    def fromstr(cls, post_content: str) -> "HugoPostSource":
        """Create a post from the string contents fo a file

        Pass in the post content as a string, including YAML frontmatter and post body.
        """
        post_content = post_content.strip()

        yaml_start_str = "---\n"
        yaml_end_str = "\n---\n"

        if not post_content.startswith(yaml_start_str):
            # No YAML frontmatter found
            return cls({}, post_content)

        yaml_start_idx = len(yaml_start_str)
        yaml_end_idx = post_content.index(yaml_end_str)
        yaml_raw = post_content[yaml_start_idx:yaml_end_idx]

        frontmatter = CaseInsensitiveDict(yaml.load(yaml_raw, yaml.Loader))

        content_start_idx = yaml_end_idx + len(yaml_end_str)
        body = post_content[content_start_idx:]

        return cls(frontmatter, body)

    def tostr(self) -> str:
        return "---\n{}---\n\n{}\n".format(yaml.dump(self.frontmatter), self.content)

    @property
    def mf2json(self):
        """Return a microformats2-parsing JSON object for the post

        https://microformats.org/wiki/microformats2-parsing
        """
        fm = copy.deepcopy(self.frontmatter)
        props = {}
        for k, v in fm.get("extra", {}).items():
            props[k.replace("_", "-")] = v
        if "title" in fm:
            props["name"] = [fm["title"]]
            del fm["title"]
        if "description" in fm:
            props["summary"] = [fm["description"]]
            del fm["description"]
        if "date" in fm:
            pubdate = fm["date"]
            if type(pubdate) == date:
                pubdate = datetime(pubdate.year, pubdate.month, pubdate.day)
            if not isinstance(pubdate, datetime):
                pubdate = datetime.fromisoformat(pubdate.replace("Z", "+00:00"))
            props["published"] = [pubdate.isoformat(timespec="seconds")]
            del fm["date"]
        if "updated" in fm:
            if not isinstance(fm["updated"], datetime):
                fm["updated"] = datetime.fromisoformat(
                    fm["updated"].replace("Z", "+00:00")
                )
            props["updated"] = [fm["updated"].isoformat(timespec="seconds")]
            del fm["updated"]
        if "tags" in fm:
            props["category"] = fm["tags"]
            del fm["tags"]
        for k, v in fm.items():
            props[k] = v
        if len(self.content.strip()) > 0:
            props["content"] = [{"markdown": self.content}]
        return {"properties": props}


class HugoBase:
    """Base class for a Hugo blog

    Makes plenty of assumptions.
    - Content is made of .md files only; cannot handle .html or .markdown or other extensions
    - Pages are always in a directory and named index.md - everything uses a Hugo pagebundle
    - Frontmatter is YAML. YAML has problems, but TOML sux, don't @ me tomlailures

    TODO: Only built for h-entry at this point
          Not sure what a more general implementation would look like

    name:               The name of the blog.
    baseuri:            The base URI of the blog, like https://blog.example.com/
    slugprefix:         Prefix for new post slugs, if any.
                        E.g. "/posts/" or "/articles" or "/blog".
                        Leading or trailing slash characters ("/") are stripped.
    collectmedia:       If true, if a post has media, move that media into the post's directory
                        after the post is uploaded.
    """

    def __init__(
        self, name: str, baseuri: str, slugprefix: str, collectmedia: bool = False
    ):
        self.name = name
        self.baseuri = normalize_baseuri(baseuri)
        self.slugprefix = slugprefix.strip("/")

        self.collectmedia = collectmedia

    def _uri2indexmd(self, uri) -> str:
        """Map a URI to an index.md in the Hugo source.

        This requries the canonical URI, not any kind of alias.
        """
        baseuri_escd = re.escape(self.baseuri)
        baseuri_re = f"^{baseuri_escd}/*"
        hugo_bundle_path = re.sub(baseuri_re, "", uri)
        if hugo_bundle_path.startswith("/"):
            hugo_bundle_path = hugo_bundle_path[1:]
        index = os.path.join("content", hugo_bundle_path, "index.md")
        return index

    def _get_raw_post_body(self, uri) -> str:
        """Subclasses must implement"""
        raise NotImplementedError("Please implement this in the subclass")

    def get_post(self, uri) -> HugoPostSource:
        raw_post = self._get_raw_post_body(uri)
        return HugoPostSource.fromstr(raw_post)

    def add_post(
        self,
        slug: str,
        frontmatter: typing.Dict,
        content: str,
        media: typing.List[str] = None,
    ) -> str:
        """Add a new post

        slug:               The slug for the post
        frontmatter:        Post frontmatter
        content:            Post body
        media:              A list of URIs representing associated media, if any.
                            If collectmedia is True, this will trigger that behavior.

        Returns the URI for the post.
        """
        if media is None:
            media = []
        post = HugoPostSource(frontmatter, content)

        # Return a good error message if the post already exists
        # Clients can modify a post by updating it, but creating a new post with the same URL as an old one should be an error
        #
        # TODO: This should probably be more complicated
        # Each blog should probably define how slugs should be handled -
        # require the client to send it, generate it from title/content, generate it from the date, something else?
        posturi = self._post_uri(slug)
        oldpost = None
        try:
            oldpost = self.get_post(posturi)
        except BaseException as exc:
            current_app.logger.debug(
                f"Could not .get_post({posturi}) due to error '{exc}'. Assuming this is correct and moving on...",
                exc_info=exc,
            )
        if oldpost is not None:
            raise MicropubDuplicatePostError(uri=posturi)

        result = self._add_raw_post_body(slug, post.tostr())

        if media and self.collectmedia:
            self._collect_media_for_post(slug, media)

        return result

    def add_post_mf2(self, mf2obj: typing.Dict):
        """Add a post from a microfotmats2 json object

        Microformats2 keeps things a little different than a Hugo blog expects,
        so we process it for Hugo first.
        """
        content = ""
        frontmatter = {}
        slug = ""
        name = ""
        props = mf2obj["properties"]
        for k, v in props.items():
            if k == "content":
                if len(v) > 1:
                    raise MicropubInvalidRequestError(
                        "Unexpectedly multiple values in content list"
                    )
                unwrappedv = v[0]
                if type(unwrappedv) is dict:
                    if len(unwrappedv) > 1:
                        raise MicropubInvalidRequestError(
                            "Unexpectedly multiple values in content dict"
                        )
                    ctype, cval = list(unwrappedv.items())[0]
                    if ctype == "html":
                        content = cval
                    elif ctype == "markdown":
                        content = cval
                    else:
                        raise MicropubInvalidRequestError(
                            f"Unexpected content type {ctype}"
                        )
                else:
                    content = unwrappedv
            elif k == "slug":
                slug = v[0]
            elif k == "name":
                name = v[0]
                frontmatter["title"] = v[0]
            else:
                frontmatter[k] = v
        if not slug:
            slug = slugify(name or content)
        if "date" not in props:
            frontmatter["date"] = datetime.utcnow().strftime("%Y-%m-%d")

        media = []
        media += props.get("photo") or []
        media += props.get("video") or []
        media += props.get("audio") or []

        return self.add_post(slug, frontmatter, content, media)

    def add_media(self, media: typing.List[FileStorage]) -> str:
        """Add one or more media files.

        media:      A list of werkzeug FileStorage objects
        """
        return self._add_media(media)

    def _post_path(self, slug: str) -> str:
        """Given a slug of a post, return the full path.

        Does not include an initial or trailing /
        """
        if slug.startswith("/"):
            slug = slug[1:]
        if self.slugprefix:
            return f"{self.slugprefix}/{slug}"
        else:
            return f"{slug}"

    def _post_uri(self, slug: str) -> str:
        """Given the slug of a post, return the full URI"""
        return f"{self.baseuri}{self._post_path(slug)}"

    def _add_raw_post_body(self, slug: str, raw_body: str) -> str:
        """Given a raw string representing the post file body, save it to the backend

        Must be implemented by a subclass.

        Must return the URI of the post.
        """
        raise NotImplementedError("Please implement this in the subclass")

    def _add_media(self, media: typing.List[FileStorage]) -> str:
        """Add media.

        Must be implemented by a subclass.

        Returns a URI to the stored location of the media.

        Blogs may save the media to this location permanently,
        or may move it to a new location once the corresponding post is submitted.
        Blogs with a separate media directory like /static/media/ would do the former,
        and posts would reference this by absolute path.

        Blogs wanting to keep a post's related media in its own folder would do the latter,
        and posts would reference media by relative path.
        These blogs should set collectmedia to True,
        and also implement the _collect_media_for_post() method (see below).
        """
        raise NotImplementedError("Please implement this in the subclass")

    def _collect_media_for_post(self, postslug: str, media: typing.List[str]):
        """Collect media for a post into the post's directory

        For blogs that want to keep a post's related media in its own folder,
        this must be implemented in a subclass.
        For blogs that save to the _add_media() location permanently,
        implementing this is not required.

        When the media endpoint is used, media is uploaded BEFORE a blog post is submitted.
        This means that at media upload time, we don't know anything about the post it is for.
        This method is called, if it is implemented, after the post is submitted.
        To implement it, move/rename the media from the temporary media storage location
        to the permanent location relative to the blog post.

        Blogs implementing this should pass collectmedia=True when they are instantiated.

        postslug:       The slug of the post, after it has been submitted.
        media:          A list of URIs to media as returned from _add_media().
                        Implementations must know how to convert those URLs to the real location;
                        e.g. a Github backend must know how to convert a raw.githubusercontent...
                        URI into a relative path for the proper repository.

        Returns None
        """
        raise NotImplementedError("Please implement this in the subclass")