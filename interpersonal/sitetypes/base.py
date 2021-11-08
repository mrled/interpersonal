"""The base class for Hugo blogs"""

import copy
import dataclasses
import os
import re
import typing
from datetime import datetime

import yaml

from interpersonal.util import CaseInsensitiveDict


@dataclasses.dataclass
class ParsedPost:
    """A post with its metadata"""

    # Frontmatter is a dict with case insensitve keys. Why?
    # Because Hugo isn't consistent and this is easier.
    frontmatter: CaseInsensitiveDict

    body: str


def parse_post_content(post_content: str) -> ParsedPost:
    """Parse metadata from contents of a post with YAML frontmatter

    Pass in the post content as a string, including YAML frontmatter and post body.
    """

    yaml_start_str = "---\n"
    yaml_end_str = "\n---\n"

    if not post_content.startswith(yaml_start_str):
        # No YAML frontmatter found
        return ParsedPost({}, post_content)

    yaml_start_idx = len(yaml_start_str)
    yaml_end_idx = post_content.index(yaml_end_str)
    yaml_raw = post_content[yaml_start_idx:yaml_end_idx]

    frontmatter = CaseInsensitiveDict(yaml.load(yaml_raw, yaml.Loader))

    content_start_idx = yaml_end_idx + len(yaml_end_str)
    body = post_content[content_start_idx:]

    return ParsedPost(frontmatter, body)


def normalize_baseuri(baseuri: str) -> str:
    """Normalize a baseuri

    If it doesn't end in a slash, add one.
    """
    if baseuri[-1] != "/":
        return baseuri + "/"
    return baseuri


class UnimplementedError(BaseException):
    pass


class HugoPostSource:
    def __init__(self, frontmatter: dict, content: str):
        self.frontmatter = frontmatter
        self.content = content

    @classmethod
    def fromstr(cls, s: str) -> "HugoPostSource":
        """Create a post from the string contents fo a file"""
        fm, body = parse_post_content(s)
        return cls(fm, body)

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
            if not isinstance(fm["date"], datetime):
                fm["date"] = datetime.fromisoformat(fm["date"].replace("Z", "+00:00"))
            props["published"] = [fm["date"].isoformat(timespec="seconds")]
        if "updated" in fm:
            if not isinstance(fm["updated"], datetime):
                fm["updated"] = datetime.fromisoformat(
                    fm["updated"].replace("Z", "+00:00")
                )
            props["updated"] = [fm["updated"].isoformat(timespec="seconds")]
        if "taxonomies" in fm and "tag" in fm["taxonomies"]:
            props["category"] = fm["taxonomies"]["tag"]
        if len(self.content.strip()) > 0:
            props["content"] = [{"markdown": self.content}]
        return {"properties": props}


class HugoBase:
    """Base class for a Hugo blog

    Makes plenty of assumptions.
    - Content is made of .md files only; cannot handle .html or .markdown or other extensions
    - Pages are always in a directory and named index.md - everything uses a Hugo pagebundle
    - Frontmatter is YAML. YAML has problems, but TOML sux, don't @ me tomlailures
    """

    def __init__(self, name: str, baseuri: str):
        self.name = name
        self.baseuri = normalize_baseuri(baseuri)

    def _uri2indexmd(self, uri) -> str:
        """Map a URI to an index.md in the Hugo source.

        This requries the canonical URI, not any kind of alias.
        """
        baseuri_re = "^" + re.escape(self.baseuri)
        hugo_bundle_path = re.sub(baseuri_re, "content/", uri)
        index = os.path.join(hugo_bundle_path, "index.md")
        return index

    def _get_raw_post_body(self, uri) -> str:
        """Subclasses must implement"""
        raise UnimplementedError

    def get_post(self, uri) -> ParsedPost:
        raw_post = self.get_raw_post_body(uri)
        return parse_post_content(raw_post)
