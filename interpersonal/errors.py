import traceback

from flask import current_app, jsonify, render_template


def json_error(errcode: int, errmsg: str, errdesc: str = ""):
    """Return JSON error"""
    current_app.logger.error(
        f"Error {errcode}: {errmsg}. Description: {errdesc or 'none'}"
    )
    return (
        jsonify({"error": errmsg, "error_description": errdesc or ""}),
        errcode,
    )


def render_error(errcode: int, errmsg: str):
    """Render an HTTP error page and log it"""
    current_app.logger.error(errmsg)
    return (
        render_template("error.html.j2", error_code=errcode, error_desc=errmsg),
        errcode,
    )


def catchall_error_handler(exc: Exception):
    """Generic error handler

    Tries to use a built-in exception handler if it exists.
    If not, writes the exception and traceback to the log and returns an
    internal server error.
    """
    try:
        result = exc.__interpersonal_exception_handler__()
    except BaseException:
        estr = "\n".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        current_app.logger.debug(
            f"catchall_error_handler(): exception '{exc}' (type {type(exc)}) does not have an __interpersonal_exception_handler__() method, returning a 500 error. Full exception detauls:\n{estr}"
        )
        result = json_error(500, "Unhandled internal error", estr)
    return result


class InvalidAuthCodeError(Exception):
    def __init__(self, code):
        self.code = code

    def __interpersonal_exception_handler__(self):
        return render_error(401, f"Invalid auth code '{self.code}'")


class IndieauthInvalidGrantError(Exception):
    def __interpersonal_exception_handler__(exc):
        return render_error(400, f"Invalid grant")


class IndieauthCodeVerifierMismatchError(Exception):
    @staticmethod
    def __interpersonal_exception_handler__(exc):
        return render_error(400, "Invalid grant: code_verified didn't match")


class IndieauthMissingCodeVerifierError(Exception):
    def __interpersonal_exception_handler__(exc):
        return render_error(400, "Missing code_verifier for S256")


class InvalidBearerTokenError(Exception):
    def __init__(self, token):
        self.token = token

    def __interpersonal_exception_handler__(self):
        return json_error(401, "unauthorized", f"Invalid bearer token '{self.token}'")


class MissingBearerAuthHeaderError(Exception):
    def __interpersonal_exception_handler__(self):
        return json_error(401, "unauthorized", "Missing Authorization header")


class AuthenticationProvidedTwiceError(Exception):
    def __interpersonal_exception_handler__(self):
        return json_error(
            401,
            "unauthorized",
            "Authentication was provided both in HTTP headers and request body",
        )


class MissingBearerTokenError(Exception):
    def __interpersonal_exception_handler__(self):
        return json_error(401, "unauthorized", "No token was provided")


class MicropubInvalidRequestError(Exception):
    def __init__(self, desc):
        self.desc = desc

    def __interpersonal_exception_handler__(self):
        return json_error(400, "invalid_request", self.desc)


class MicropubInsufficientScopeError(Exception):
    def __init__(self, action):
        self.action = action

    def __interpersonal_exception_handler__(self):
        return json_error(
            403,
            "insufficient_scope",
            f"Access token not valid for action '{self.action}'",
        )


class MicropubBlogNotFoundError(Exception):
    def __init__(self, blog_name):
        self.blog_name = blog_name

    def __interpersonal_exception_handler__(self):
        return render_error(404, f"No such blog configured: {self.blog_name}")


class MicropubDuplicatePostError(Exception):
    def __init__(self, uri: str = ""):
        self.uri = uri

    def __str__(self):
        return f"A post with URI <{self.uri}> already exists"

    def __interpersonal_exception_handler__(self):
        return json_error(400, "invalid_request", str(self))


class InterpersonalNotFoundError(Exception):
    def __interpersonal_exception_handler__(self):
        return json_error(404, "Not found", str(self))
