"""Interpersonal utility functions"""

from urllib.parse import parse_qs, urlencode, urlparse
import functools
import typing
from fastcore.basics import strcat

from flask import current_app, jsonify, render_template
from flask.helpers import url_for


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


# def qsargs(*names, **names_and_processors):
#     """Decorator so that Flask routes can use query strings as function parameters

#     <https://stackoverflow.com/questions/34587634/get-query-string-as-function-parameters-on-flask>

#     Without this, to access the query string from a Flask function,
#     you would do something like:

#         @app.route("/whatever")
#         def whatever():
#             asdf = request.get("asdf", "some-default-value")
#             age = int(request.get("age"))
#             return f"You got one {asdf} aged {age}"

#     For functions wrapped with this, it's a little nicer and more natural Python:

#         @app.route("/whatever")
#         @qsargs("asdf", age=int)
#         def whatever(asdf, age):
#             return f"You got one {asdf} aged {age}"

#     """
#     user_args = [{"key": name} for name in names] + [
#         {"key": key, "type": processor}
#         for (key, processor) in names_and_processors.items()
#     ]

#     def args_from_request(to_extract, provided_args, provided_kwargs):
#         # Ignoring provided_* here - ideally, you'd merge them
#         # in whatever way makes the most sense for your application
#         result = {}
#         for arg in to_extract:
#             result[arg["key"]] = request.args.get(**arg)
#         return provided_args, result

#     def decorator(f):
#         @functools.wraps(f)
#         def wrapper(*args, **kwargs):
#             final_args, final_kwargs = args_from_request(user_args, args, kwargs)
#             return f(*final_args, **final_kwargs)

#         return wrapper

#     return (
#         decorator if len(names) < 1 or not callable(names[0]) else decorator(names[0])
#     )


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


# def absolute_url_for(current_app, view, **kwargs):
#     """Generate an absolute URL for a view.

#     Takes a view function name, like `flask.url_for`, and returns that view
#     function's URL prefixed with the full & correct scheme and domain.

#     via: <https://github.com/pallets/flask/issues/824#issuecomment-302904753>

#     Unfortunately Flask doesn't offer this functionality.
#     Needed at least for verifying the bearer token, where the micropub server
#     must make a request to the indieauth server.
#     """
#     parsed_url = urlparse(url_for(view, _external=True, **kwargs))
#     app_scheme = urlparse(current_app.config["HOST"]).scheme
#     final_parsed_url = parsed_url._replace(scheme=app_scheme)
#     return final_parsed_url.geturl()


def parse_opt_scope_list(scopes: typing.Optional[str]) -> typing.List[str]:
    """Parse scope input

    Scopes might not be specified, or might be a space separated list.

    If a scope is not specified, it means 'create'.
    """
    if scopes:
        return scopes.split(" ")
    return ["create"]