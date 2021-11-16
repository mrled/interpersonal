"""The base class for Hugo blogs"""

import copy
import os
import re
import typing
from datetime import date, datetime

import yaml

from interpersonal.util import CaseInsensitiveDict


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
        return "\n---\n{}\n---\n\n{}".format(yaml.dump(self.frontmatter), self.content)

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
        if "description" in fm:
            props["summary"] = [fm["description"]]
        if "date" in fm:
            pubdate = fm["date"]
            if type(pubdate) == date:
                pubdate = datetime(pubdate.year, pubdate.month, pubdate.day)
            if not isinstance(pubdate, datetime):
                pubdate = datetime.fromisoformat(pubdate.replace("Z", "+00:00"))
            props["published"] = [pubdate.isoformat(timespec="seconds")]
        if "updated" in fm:
            if not isinstance(fm["updated"], datetime):
                fm["updated"] = datetime.fromisoformat(
                    fm["updated"].replace("Z", "+00:00")
                )
            props["updated"] = [fm["updated"].isoformat(timespec="seconds")]
        if "tags" in fm:
            props["category"] = fm["tags"]
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

    def __init__(self, name: str, baseuri: str):
        self.name = name
        self.baseuri = normalize_baseuri(baseuri)

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
        return self._add_raw_post_body(slug, post.tostr())

    def _add_raw_post_body(self, slug: str, raw_body: str):
        raise NotImplementedError("Please implement this in the subclass")
