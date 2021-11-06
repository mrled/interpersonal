"""Manage Interpersonal configuration"""

import dataclasses
import typing

import yaml


@dataclasses.dataclass
class BlogGithubRepo:
    github_repo: str
    github_token: str


class BlogExample:
    pass


@dataclasses.dataclass
class Blog:
    name: str
    uri: str
    type: typing.Union[BlogExample, BlogGithubRepo]


@dataclasses.dataclass
class AppConfig:
    """Application configuration"""

    loglevel: str
    database: str
    password: str
    owner_profile: str
    cookie_secret_key: str
    blogs: typing.List[Blog]

    @classmethod
    def fromyaml(cls, path: str) -> "AppConfig":
        """Create a new AppConfig instance from a YAML file path

        Note that debug logging may not yet be available
        """
        with open(path) as fp:
            yamlcontents = yaml.load(fp, yaml.Loader)

        blogs: typing.List[Blog] = []
        for yamlblog in yamlcontents["blogs"]:
            if yamlblog["type"] == "built-in example":
                blogtype = BlogExample()
                uri = "http://example.com/blog"
            elif yamlblog["type"] == "github":
                blogtype = BlogGithubRepo(
                    yamlblog["github_repo"], yamlblog["github_token"]
                )
                uri = yamlblog["uri"]
            else:
                raise Exception(f"Unknown blog type {yamlblog['type']}")
            blogs += [Blog(yamlblog["name"], uri, blogtype)]

        loglevel = yamlcontents.get("loglevel", "INFO")
        db = yamlcontents["database"]
        cookie_secret_key = yamlcontents["cookie_secret_key"]
        password = yamlcontents["password"]
        owner_profile = yamlcontents["owner_profile"]
        return cls(loglevel, db, password, owner_profile, cookie_secret_key, blogs)

    def blog(self, name: str) -> Blog:
        """Get a blog by name"""
        for blog in self.blogs:
            if blog.name == name:
                return blog
            raise KeyError(f"No blog with name '{name}'")
