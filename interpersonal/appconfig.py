"""Manage Interpersonal configuration"""

import dataclasses
import typing

import yaml

from interpersonal.errors import MicropubBlogNotFoundError
from interpersonal.sitetypes import example, github
from interpersonal.sitetypes.base import HugoBase


@dataclasses.dataclass
class AppConfig:
    """Application configuration"""

    loglevel: str
    database: str
    password: str
    cookie_secret_key: str
    blogs: typing.List[HugoBase]

    @classmethod
    def fromyaml(cls, path: str) -> "AppConfig":
        """Create a new AppConfig instance from a YAML file path

        Note that debug logging may not yet be available
        """
        with open(path) as fp:
            yamlcontents = yaml.load(fp, yaml.Loader)

        blogs: typing.List[HugoBase] = []
        for yamlblog in yamlcontents["blogs"]:
            if yamlblog["type"] == "built-in example":
                blog = example.HugoExampleBlog(
                    yamlblog["name"],
                    yamlblog["uri"],
                    yamlblog["slugprefix"],
                    yamlblog["mediaprefix"],
                )
            elif yamlblog["type"] == "github":
                blog = github.HugoGithubRepo(
                    yamlblog["name"],
                    yamlblog["uri"],
                    yamlblog["slugprefix"],
                    yamlblog["mediaprefix"],
                    yamlblog["github_owner"],
                    yamlblog["github_repo"],
                    yamlblog["github_repo_branch"],
                    yamlblog["github_app_id"],
                    yamlblog["github_app_private_key"],
                )
            else:
                raise Exception(f"Unknown blog type {yamlblog['type']}")
            blogs += [blog]

        loglevel = yamlcontents.get("loglevel", "INFO")
        db = yamlcontents["database"]
        cookie_secret_key = yamlcontents["cookie_secret_key"]
        password = yamlcontents["password"]
        return cls(loglevel, db, password, cookie_secret_key, blogs)

    def blog(self, name: str) -> HugoBase:
        """Get a blog by name"""
        for blog in self.blogs:
            if blog.name == name:
                return blog
        raise MicropubBlogNotFoundError(name)
