"""Interpersonal utility functions"""

from urllib.parse import parse_qs, urlencode, urlparse
import typing


def querystr(d: typing.Dict, prefix=False) -> str:
    """Given a dictionary, return a query string

    d: A dict
    prefix: If true and d is not empty, prefix with '?'.
    """
    qs = urlencode(d)
    if qs:
        if prefix:
            return f"?{qs}"
        else:
            return qs
    else:
        return ""


def uri(u: str, d: typing.Dict = None) -> str:
    """Create a URL with an optional query string

    u: A URL without query string, like https://example.com/asdf
    d: An optional dict
    """
    qs = querystr(d, prefix=True)
    return f"{u}{qs}"


def uri_copy_and_append_query(u: str, d: typing.Dict = None) -> str:
    """Given a URI and an optional dictionary, append the dict to the URI's query string

    u: URI
    d: Dict
    """
    parsed_u = urlparse(u)

    qs = {}
    for k, v in parse_qs(parsed_u.query).items():
        # parse_qs makes a SINGLE ITEM ARRAY for every value
        # I guess this is because some things can have more than one value?
        # Not sure there's a standard for that and it doesn't apply to us in this app I think.
        qs[k] = v[0]
    if d is not None:
        for k, v in d.items():
            qs[k] = v

    return uri(f"{parsed_u.scheme}://{parsed_u.netloc}{parsed_u.path}", d=qs)


class CaseInsensitiveDict(dict):
    """A dict where keys are case insensitive

    Adapted from <https://stackoverflow.com/a/32888599/868206>
    """

    @classmethod
    def _k(cls, key):
        return key.lower() if isinstance(key, str) else key

    def __init__(self, *args, **kwargs):
        super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(self.__class__._k(key))

    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(self.__class__._k(key), value)

    def __delitem__(self, key):
        return super(CaseInsensitiveDict, self).__delitem__(self.__class__._k(key))

    def __contains__(self, key):
        return super(CaseInsensitiveDict, self).__contains__(self.__class__._k(key))

    def has_key(self, key):
        return super(CaseInsensitiveDict, self).has_key(self.__class__._k(key))

    def pop(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).pop(
            self.__class__._k(key), *args, **kwargs
        )

    def get(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).get(
            self.__class__._k(key), *args, **kwargs
        )

    def setdefault(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).setdefault(
            self.__class__._k(key), *args, **kwargs
        )

    def update(self, E=None, **F):
        super(CaseInsensitiveDict, self).update(self.__class__(E or {}))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))

    def _convert_keys(self):
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(k, v)
