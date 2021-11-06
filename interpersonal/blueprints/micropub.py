"""Blueprint for a micropub endpoint implementation.

Kept separate from indieauth, but note that it must know of the indieauth token
endpoint in advance, so there is some coupling.
"""

import json
import re

import requests
from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    render_template,
    request,
    session,
    url_for,
)

from interpersonal import database, util
from interpersonal.blueprints.indieauth import (
    ALL_HTTP_METHODS,
    COOKIE_INDIE_AUTHED,
    indieauth_required,
)


bp = Blueprint("micropub", __name__, url_prefix="/micropub")


def json_error(errcode: int, errmsg: str):
    """Return JSON error"""
    current_app.logger.error(errmsg)
    return (
        jsonify({"error": errmsg}),
        errcode,
    )


def render_error(errcode: int, errmsg: str):
    """Render an HTTP error page and log it"""
    current_app.logger.error(errmsg)
    return (
        render_template("error.html.j2", error_code=errcode, error_desc=errmsg),
        errcode,
    )


# TODO: code duplication from indieauth blueprint, can I fix?
@bp.before_app_request
def load_logged_in_user():
    """Determine whether user is logged in before any view function runs

    It is safe to do this in the cookie, because we are using encrypted cookies.
    """
    g.indieauthed = session.get(COOKIE_INDIE_AUTHED) is not None


# TODO: add tests
def verify_indieauth_access_token(token):
    """Verify an IndieAuth access token (bearer token)

    <https://indieweb.org/token-endpoint#Verifying_an_Access_Token>

    Note that per that link:

    > The URL of the token server must be known to the micropub endpoint in advance. The bearer token does not contain any information about the server address.
    > This means that the micropub endpoint dictates the token endpoint that the user links to on his homepage.

    This couples our micropub implementation (this blueprint)
    to our indieauth implementation (the indieauth blueprint).

    Note that this coupling means we COULD verify the token internally.

    > Token-endpoints like https://tokens.indieauth.com that aim to interoperate with different micropub endpoint implementations MUST support this standard mechanism for verifying the token. However, if the token and micropub endpoints are tightly coupled (i.e. you control both implementations and expect them only to talk to each other), this verification can be done internally.

    However, for now I'm going to do it as if these were two separate implementations. I'll learn it better this way, and it'll be more useful as an example to other implementors.
    """

    token_endpoint = url_for("indieauth.token")
    response = requests.get(
        token_endpoint, headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
    verified_token = json.loads(response.content.decode())
    return verified_token


@bp.route("/")
@indieauth_required(ALL_HTTP_METHODS)
def index():
    """The index page for the micropub blueprint

    Show a list of configured blogs
    """
    blogs = current_app.config["APPCONFIG"].blogs
    # TODO: show example blog correctly (no github link)
    return render_template("micropub/index.html.j2", blogs=blogs)


# TODO: add tests
def micropub_blog_endpoint_GET():
    """The GET verb for the micropub index route"""
    token = re.sub("Bearer ", "", request.headers["Authorization"])

    if not token:
        return json_error(401, "unauthorized")

    try:
        verified_token = verify_indieauth_access_token(token)
    except:
        return json_error(401, "unauthorized")

    # TODO: not sure how I know that the user is valid?

    q = request.args.get("q")
    if q == "config":
        return jsonify(
            {
                "media-endpoint": url_for(".media"),
            }
        )
    elif q == "source":
        url = request.args.get("url")
        if not url:
            return json_error(400, "invalid_request")


# TODO: add tests
@bp.route("/<blog_name>")
@indieauth_required(["GET"])
def micropub_blog_endpoint(blog_name):
    """The micropub endpoint

    Note that bearer_GET requires authentication in the
    """
    try:
        blog = current_app.config["APPCONFIG"].blog(blog_name)
    except KeyError:
        return render_error(404, f"No such blog configured: {blog_name}")
    if request.method == "GET":
        return micropub_blog_endpoint_GET(blog)
    if request.method == "POST":
        return micropub_blog_endpoint_POST(blog)
