"""The base class for Hugo blogs"""

import copy
from dataclasses import dataclass
import hashlib
import os
import re
import typing
from datetime import date, datetime

import yaml
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from interpersonal.errors import (
    InterpersonalConfigurationError,
    MicropubDuplicatePostError,
    MicropubInvalidRequestError,
)
from interpersonal.util import CaseInsensitiveDict, extension_from_content_type


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


@dataclass
class AddedMediaItem:
    """A media item added to the blog

    uri:        The URI that it is reachable at
    created:    True if just created (HTTP code should be 201),
                False if it already existed and was not reuploaded (HTTP code 200)
    """

    uri: str
    created: bool


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


@dataclass
class HugoDirectories:
    """Directories used by Hugo"""

    content: str
    static: str


class OpaqueFile:
    """A simple file class for e.g. uploaded files."""

    def __init__(self, file_storage: FileStorage):
        self.contents = file_storage.read()

        self.content_type = file_storage.content_type
        self._uploaded_filename_UNSAFE = file_storage.filename or None

        hash = hashlib.sha256(usedforsecurity=False)
        hash.update(self.contents)
        self.digest = hash.digest()
        self.hexdigest = hash.hexdigest()

    @property
    def filename(self) -> str:
        """Get the filename to use when storing a media item"""
        if self._uploaded_filename_UNSAFE:
            secname = secure_filename(self._uploaded_filename_UNSAFE)
            basename = os.path.splitext(os.path.basename(secname))[0]
        else:
            basename = "item"
        # E.g. an image with a .jpg extension will be saved with the .jpeg extension.
        ext = extension_from_content_type(self.content_type)
        return f"{basename}.{ext}"


class HugoBase:
    """Base class for a Hugo blog

    Makes plenty of assumptions.
    - Content is made of .md files only; cannot handle .html or .markdown or other extensions
    - Pages are always in a directory and named index.md - everything uses a Hugo pagebundle
    - Frontmatter is YAML. YAML has problems, but TOML sux, don't @ me tomlailures

    TODO: Only built for h-entry at this point
          Not sure what a more general implementation would look like

    About media:
    (TODO: Test this)
    This class and its subclasses can operate in one of two modes:

    - Dedicated Media Location Mode.
      Media is saved to some dedicated space, not connected to the post that references it.
      In this mode, media is accessible via a URI like
      `https://your-blog.example.com/<mediaprefix>/<hash>/<filename>.jpeg`.
      When media is uploaded, it is added to the blog backend (e.g. Github) immediately.
      To enable this mode, set `mediaprefix` and do not set `mediastaging`.

    - Staged Media Mode.
      Media is staged by Interpersonal itself, and when a post is created that references it,
      the post and media are saved to the blog backend (e.g. uploaded to Github) at the same time.
      In this mode, media is saved next to the post that references it.
      This means that on initial upload, media will have a URI from Interpersonal, like
      `https://interpersonal.example.com/microblog/your-blog/staging/<hash>/<filename>.jpeg`,
      and only when the post is created will it have a URI from your blog,
      which will be under the post that references it, like
      `https://your-blog.example.com/<slugprefix>/<post slug>/<hash>/<filename>.jpeg`.
      To enable this mode, set `mediastaging` and do not set `mediaprefix`.

    name:               The name of the blog.
    baseuri:            The base URI of the blog, like https://blog.example.com/
    interpersonal_uri:  The base URI of interpersonal itself,
                        like https://interpersonal.example.com/.
    slugprefix:         Prefix for new post slugs, if any.
                        E.g. "/posts/" or "/articles" or "/blog".
                        Leading or trailing slash characters ("/") are stripped.
    mediaprefix:        Prefix for blog media.
                        E.g. "/media/" or "/uploads".
                        Leading or trailing slash characters ("/") are stripped.
    mediastaging:       Optional location on the local filesystem for a media staging area.
                        E.g. "/var/www/interpersonal/mediastaging".
    """

    def __init__(
        self,
        name: str,
        baseuri: str,
        interpersonal_uri: str,
        slugprefix: str,
        *,
        mediaprefix: str = "",
        mediastaging: str = "",
    ):
        if (mediaprefix and mediastaging) or not (mediaprefix or mediastaging):
            raise InterpersonalConfigurationError(
                "Must pass exactly one of 'mediaprefix' or 'mediastaging'"
            )
        self.name = name
        self.baseuri = normalize_baseuri(baseuri)
        self.interpersonal_uri = normalize_baseuri(interpersonal_uri)
        self.slugprefix = slugprefix.strip("/")
        self.mediaprefix = mediaprefix.strip("/")
        self.mediastaging = mediastaging
        self.dirs = HugoDirectories("content", "static")

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
                            If mediastaging is set, this function will trigger media collection.

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

        if media and self.mediastaging:
            post_raw_str = self._collect_media_for_post(slug, post.tostr(), media)
        else:
            post_raw_str = post.tostr()

        result = self._add_raw_post_body(slug, post_raw_str)

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

    def add_media(self, media: typing.List[FileStorage]) -> typing.List[AddedMediaItem]:
        """Add one or more media files.

        media:      A list of werkzeug FileStorage objects
        """
        processed_media = [OpaqueFile(m) for m in media]
        return self._add_media(processed_media)

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

    def _add_media(self, media: typing.List[OpaqueFile]) -> str:
        """Add media.

        Must be implemented by a subclass.

        Returns a URI to the stored location of the media.

        Blogs may save the media to this location permanently,
        or may move it to a new location once the corresponding post is submitted.
        Blogs with a separate media directory like /static/media/ would do the former,
        and posts would reference this by absolute path.

        Blogs wanting to keep a post's related media in its own folder would do the latter,
        and posts would reference media by relative path.
        These blogs should set 'mediastaging' to a directory,
        and also implement the _collect_media_for_post() method (see below).
        """
        raise NotImplementedError("Please implement this in the subclass")

    def _collect_media_for_post(
        self, postslug: str, postbody: str, media: typing.List[str]
    ) -> str:
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

        Blogs implementing this should set 'mediastaging' when they are instantiated.

        postslug:       The slug of the post, after it has been submitted.
        postbody:       The raw string body of the post.
                        This is the raw representation of the post, including frontmatter etc.
        media:          A list of URIs to media as returned from _add_media().
                        Implementations must know how to convert those URLs to the real location;
                        e.g. a Github backend must know how to convert a raw.githubusercontent...
                        URI into a relative path for the proper repository.

        It must return a modified postbody, with all media URIs replaced with their new locations.
        """
        raise NotImplementedError("Please implement this in the subclass")

    def _media_item_uri_mediadir(self, media_item: OpaqueFile) -> str:
        """Get the URI for an item relative to the media dir

        For sites that use Staged Media Mode.
        This is the permanent URI, and it does not change after being uploaded.
        """
        return f"{self.baseuri}{self.mediaprefix}/{media_item.hexdigest}/{media_item.filename}"

    def _media_item_uri_staging(self, media_item: OpaqueFile) -> str:
        """Get the staging URI for a media item

        For sites that use Staged Media Mode.
        Return a temporary URI that is valid until media is collected.
        """
        return f"{self.interpersonal_uri}micropub/{self.name}/staging/{media_item.hexdigest}/{media_item.filename}"

    def _media_item_uri_collected(
        self, slug: str, media_item: typing.Union[OpaqueFile, str]
    ) -> str:
        """Get the post-collection URI (under a particular post) for a media item

        For sites that use Staged Media Mode.
        This is the permanent URI, but images are not available at this URI
        until after _collect_media_for_post() is called.

        Unlike other _media_item_...() functions, `media_item` may be a string.
        If it is a string, it is assumed to be the staging URI for an image,
        and the file hash and filename are extracted from it.
        """
        if type(media_item) is str:
            splituri = media_item.split("/")
            digest = splituri[-2]
            filename = splituri[-1]
        else:
            digest = media_item.hexdigest
            filename = media_item.filename
        return f"{self.baseuri}{self.slugprefix}/{slug}/{digest}/{filename}"

    def _add_media_staging(
        self, media: typing.List[OpaqueFile]
    ) -> typing.List[AddedMediaItem]:
        """Add media to an internal media staging area.

        This is a helper method that subclasses may use if they like, or not.

        When media is uploaded to the media endpoint, the post has not yet been created.
        Media must be saved somewhere regardless.
        A subclass may choose to save to a dedicated media space like /media/...,
        in which case the subclass's ._add_media() implementation
        simply saves it there and is done.
        Alternatively, a subclass may choose to call _this_ method,
        which saves media to a staging location, in their ._add_media(),
        and also implement ._collect_media(), which is called after a post is created,
        and which will move media from the staging implementation to the final location.

        For sites that use Staged Media Mode.
        """

        if not self.mediastaging:
            raise Exception(f"mediastaging was not set for blog {self.blog}")
        if not os.path.isdir(self.mediastaging):
            raise Exception(
                f"Media staging path {self.mediastaging} does not exist (or is not a directory)"
            )

        result: typing.List[AddedMediaItem] = []
        for item in media:
            digest = item.hexdigest
            parent = os.path.join(self.mediastaging, digest)
            path = os.path.join(parent, item.filename)
            if os.path.exists(path):
                created = False
            else:
                created = True
                parent = os.path.split(path)[0]
                os.makedirs(parent)
                with open(path, "wb") as fp:
                    fp.write(item.contents)
            uri = f"{self.interpersonal_uri}micropub/{self.name}/media/{digest}/{item.filename}"
            result.append(AddedMediaItem(uri, created))

        return result
