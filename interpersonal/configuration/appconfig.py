"""Manage Interpersonal configuration"""

import dataclasses
import os.path
import typing

import yaml

from interpersonal.configuration.basetypes import SiteSectionMap
from interpersonal.errors import (
    InterpersonalConfigurationError,
    MicropubBlogNotFoundError,
)
from interpersonal.sitetypes import example, github
from interpersonal.sitetypes.base import HugoBase


@dataclasses.dataclass
class AppConfig:
    """Application configuration"""

    loglevel: str
    database: str
    password: str
    mediastaging: str
    cookie_secret_key: str
    csp_remote_trusted_sources: typing.List[str]
    blogs: typing.List[HugoBase]

    @classmethod
    def fromyaml(cls, path: str) -> "AppConfig":
        """Create a new AppConfig instance from a YAML file path

        Note that debug logging may not yet be available
        """
        with open(path) as fp:
            yamlcontents = yaml.load(fp, yaml.Loader)

        key_exc = None
        try:
            interpersonal_uri = yamlcontents["uri"]
            loglevel = yamlcontents.get("loglevel", "INFO")
            db = yamlcontents["database"]
            cookie_secret_key = yamlcontents["cookie_secret_key"]
            password = yamlcontents["password"]
            yamlblogs = yamlcontents["blogs"]
            mediastaging_base = yamlcontents["mediastaging"]
            csp_remote_trusted_sources = yamlcontents.get(
                "csp_remote_trusted_sources", []
            )
        except KeyError as exc:
            key_exc = exc
        if key_exc:
            raise InterpersonalConfigurationError(
                f"Missing required configuration setting '{key_exc.args[0]}'"
            )

        if not mediastaging_base or not os.path.isdir(mediastaging_base):
            raise InterpersonalConfigurationError(
                f"Media staging directory {mediastaging_base} does not exist"
            )

        blogs: typing.List[HugoBase] = []
        for yamlblog in yamlblogs:
            key_exc = None

            blog_name = yamlblog.get("name")
            if not blog_name:
                raise InterpersonalConfigurationError(
                    f"A blog is defined without its 'name' being set"
                )

            mediaprefix = yamlblog.get("mediaprefix", "")
            mediastaging_sub = ""
            if not mediaprefix:
                mediastaging_sub = os.path.join(mediastaging_base, blog_name)

            key_exc = None
            type_exc = None
            try:
                sectionmap = SiteSectionMap(yamlblog["sectionmap"])
            except KeyError as exc:
                key_exc = exc
            except TypeError as exc:
                type_exc = exc
            if key_exc or type_exc:
                # TODO: Point to documentation with detailed examples of valid configs
                raise InterpersonalConfigurationError(
                    f"Blog {blog_name} has invalid or missing sectionmap configuration, check its configuration and make sure it has a 'sectionmap' setting that at least contains a 'post' mapping."
                )

            try:
                if yamlblog["type"] == "built-in example":
                    blog = example.HugoExampleBlog(
                        yamlblog["name"],
                        yamlblog["uri"],
                        interpersonal_uri,
                        sectionmap,
                        mediaprefix=mediaprefix,
                        mediastaging=mediastaging_sub,
                    )
                elif yamlblog["type"] == "github":
                    blog = github.HugoGithubRepo(
                        yamlblog["name"],
                        yamlblog["uri"],
                        interpersonal_uri,
                        sectionmap,
                        yamlblog["github_owner"],
                        yamlblog["github_repo"],
                        yamlblog["github_repo_branch"],
                        yamlblog["github_app_id"],
                        yamlblog["github_app_private_key"],
                        mediaprefix=mediaprefix,
                        mediastaging=mediastaging_sub,
                    )
                else:
                    raise InterpersonalConfigurationError(
                        f"Unknown blog type {yamlblog['type']}"
                    )
            except KeyError as exc:
                key_exc = exc

            if key_exc:
                raise InterpersonalConfigurationError(
                    f"Blog {blog_name} missing required configuration setting '{key_exc.args[0]}'"
                )
            blogs += [blog]

        return cls(
            loglevel,
            db,
            password,
            mediastaging_base,
            cookie_secret_key,
            csp_remote_trusted_sources,
            blogs,
        )

    def blog(self, name: str) -> HugoBase:
        """Get a blog by name"""
        for blog in self.blogs:
            if blog.name == name:
                return blog
        raise MicropubBlogNotFoundError(name)
