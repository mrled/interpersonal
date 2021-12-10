import dataclasses
import typing

from interpersonal.errors import InterpersonalConfigurationError


@dataclasses.dataclass
class SiteSectionMap:
    """A mapping of content types to site sections.

    See docs/sectionmap.md for more details.

    Initializer arguments:

    mapping:    A mapping of situation names to content types.
                MUST include a 'default' key.
                A "situation name" might be "bookmark", for Micropub posts that contain bookmark-of.
                TODO: Add handlers for more situations

    Properties:

    default:    The default content type, e.g. "blog"
    mapping:    A mapping of
    """

    def __init__(self, mapping: typing.Dict[str, str]):
        key_exc = None
        try:
            default = mapping["default"]
        except KeyError as exc:
            key_exc = exc
        if key_exc:
            raise InterpersonalConfigurationError(
                f"No 'default' value found in site section map"
            )
        self.default = default
        self.mapping = mapping

    def get(self, key: str) -> str:
        """Get a value from the mapping, falling back to the default"""
        return self.mapping.get(key, self.default)
