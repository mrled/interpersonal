"""The base class for Hugo blogs"""

import copy
import os
import re
import typing
from datetime import date, datetime

import yaml
from flask import current_app

from interpersonal.errors import MicropubDuplicatePostError
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
    """

    def __init__(self, name: str, baseuri: str, slugprefix: str):
        self.name = name
        self.baseuri = normalize_baseuri(baseuri)

        # slugprefix should never have leading or trailing / so that it's easier to work with.
        # e.g., a slugprefix of /blog/ should be saved here as simply "blog".
        self.slugprefix = slugprefix.strip("/")

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

    def add_post(self, slug: str, frontmatter: typing.Dict, content: str) -> str:
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
                f"Could not .get_post({posturi}) due to error '{exc}'. Assuming this is correct and moving on..."
            )
            current_app.logger.exception(exc)
        if oldpost is not None:
            raise MicropubDuplicatePostError(uri=posturi)

        return self._add_raw_post_body(slug, post.tostr())

    def add_post_mf2(self, mf2obj: typing.Dict):
        """Add a post from a microfotmats2 json object"""
        content = ""
        frontmatter = {}
        slug = ""
        name = ""
        for k, v in mf2obj["properties"].items():
            if k == "content":
                content = v[0]
            elif k == "slug":
                slug = v[0]
            elif k == "name":
                name = v[0]
                frontmatter["title"] = v[0]
            else:
                frontmatter[k] = v
        if not slug:
            slug = slugify(name or content)
        if "date" not in mf2obj["properties"]:
            frontmatter["date"] = datetime.utcnow().strftime("%Y-%m-%d")
        return self.add_post(slug, frontmatter, content)

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

    def _add_raw_post_body(self, slug: str, raw_body: str):
        raise NotImplementedError("Please implement this in the subclass")
