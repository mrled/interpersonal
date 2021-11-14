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


class InvalidBearerTokenError(Exception):
    def __init__(self, token):
        self.token = token

    @staticmethod
    def handler(exc):
        return json_error(401, "unauthorized", f"Invalid bearer token '{exc.token}'")


class MissingBearerAuthHeaderError(Exception):
    @staticmethod
    def handler(exc):
        return json_error(401, "unauthorized", "Missing Authorization header")


class MissingBearerTokenError(Exception):
    @staticmethod
    def handler(exc):
        return json_error(401, "unauthorized", "No token was provided")


class MicropubInvalidRequestError(Exception):
    def __init__(self, desc):
        self.desc = desc

    @staticmethod
    def handler(exc):
        return json_error(400, "invalid_request", exc.desc)


class MicropubInsufficientScopeError(Exception):
    def __init__(self, action):
        self.action = action

    @staticmethod
    def handler(exc):
        return json_error(
            403,
            "insufficient_scope",
            f"Access token not valid for action '{exc.action}'",
        )


class MicropubBlogNotFoundError(Exception):
    def __init__(self, blog_name):
        self.blog_name = blog_name

    @staticmethod
    def handler(exc):
        return render_error(404, f"No such blog configured: {self.blog_name}")