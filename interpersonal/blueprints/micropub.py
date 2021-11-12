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

from interpersonal import util
from interpersonal.blueprints.indieauth import (
    ALL_HTTP_METHODS,
    COOKIE_INDIE_AUTHED,
    InvalidBearerTokenError,
    bearer_verify_token,
    indieauth_required,
)
from interpersonal.sitetypes.base import HugoBase
from interpersonal.util import render_error, json_error


bp = Blueprint("micropub", __name__, url_prefix="/micropub")


# TODO: code duplication from indieauth blueprint, can I fix?
@bp.before_app_request
def load_logged_in_user():
    """Determine whether user is logged in before any view function runs

    It is safe to do this in the cookie, because we are using encrypted cookies.
    """
    g.indieauthed = session.get(COOKIE_INDIE_AUTHED) is not None


# TODO: add tests
def verify_indieauth_access_token_via_http(token):
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

    token_endpoint = util.absolute_url_for(current_app, "indieauth.bearer")
    # token_endpoint = url_for("indieauth.bearer")
    current_app.logger.debug(f"Verifying access token via endpoint {token_endpoint}")
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
    return render_template("micropub/index.html.j2", blogs=blogs)


class MissingBearerAuthHeaderError(BaseException):
    pass


class MissingBearerTokenError(BaseException):
    pass


def bearer_verify_token_from_auth_header(auth_header: str):
    """Given an Authorization header, verify the token.

    Return a VerifiedBearerToken.

    Raises exceptions if verification fails.
    """
    if not auth_header:
        raise MissingBearerAuthHeaderError

    token = re.sub("Bearer ", "", auth_header)
    if not token:
        raise MissingBearerTokenError

    verified = bearer_verify_token(token)
    current_app.logger.debug(
        f"Successfully verified token {token} for owner {verified['me']} using client {verified['client_id']} authorized for scope {verified['scopes']}"
    )

    return verified


def micropub_blog_endpoint_GET(blog: HugoBase):
    """The GET verb for the micropub blog route

    Used by clients to:
    * Retrieve the configuration, including the media-endpoint and any syndication targets
      (syndication targets currently not supported)
    * Retrieve metadata for a given URL, such as published date and tags, in microformats2-json format
    """

    try:
        verified = bearer_verify_token_from_auth_header(
            request.headers.get("Authorization")
        )
    except MissingBearerAuthHeaderError:
        return json_error(401, "unauthorized", "Missing Authorization header")
    except MissingBearerTokenError:
        return json_error(401, "unauthorized", "No token was provided")
    except InvalidBearerTokenError as exc:
        current_app.logger.debug(exc)
        return json_error(401, "unauthorized", exc)
    except BaseException as exc:
        current_app.logger.debug(f"Unexpected exception: {exc}")
        return json_error(500, "internal_server_error", exc)

    q = request.args.get("q")

    current_app.logger.debug(f"Micropub endpoint with q={q}")

    # The micropub endpoint configuration
    if q == "config":
        return jsonify(
            {
                "media-endpoint": url_for(
                    "micropub.micropub_blog_media", blog_name=blog.name
                ),
            }
        )

    # Properties for a given "source", aka metadata for a given URL
    # e.g. tags, title, publish date, ... for a blog post
    # TODO: we ignore requests for specific properties and always return all properties, should we change this?
    elif q == "source":
        url = request.args.get("url")
        if not url:
            return json_error(
                400, "invalid_request", "Required 'url' parameter missing"
            )
        try:
            post = blog.get_post(url)
            return jsonify(post.frontmatter)
        # TODO: Raise a specific error in the blog object when a post is not found
        except KeyError:
            return json_error(404, "no such blog post")
        except BaseException as exc:
            return json_error(500, "internal server error", exc)

    elif q == "syndicate-to":
        return json_error(400, "invalid_request", "syndication is not implemented")

    else:
        return json_error(
            400,
            "invalid_request",
            "Valid authorization, but invalid or missing 'q' parameter",
        )


def micropub_blog_endpoint_POST(blog: HugoBase):
    """The POST verb for the micropub blog route

    Used by clients to change content (CRUD operations on posts)
    """
    try:
        form_encoded = request.headers.get("Content-type") in [
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ]
        form_auth_token = request.form.get("auth_token")
        if form_encoded and form_auth_token:
            verified = bearer_verify_token(form_auth_token)
        else:
            verified = bearer_verify_token_from_auth_header(
                request.headers.get("Authorization")
            )
    except MissingBearerAuthHeaderError:
        return json_error(401, "unauthorized", "Missing Authorization header")
    except MissingBearerTokenError:
        return json_error(401, "unauthorized", "No token was provided")
    except InvalidBearerTokenError as exc:
        current_app.logger.debug(exc)
        return json_error(401, "unauthorized", exc)
    except BaseException as exc:
        current_app.logger.debug(f"Unexpected exception: {exc}")
        return json_error(500, "internal_server_error", exc)

    auth_test = request.headers.get("X-Interpersonal-Auth-Test")
    # Check for the header we use in testing, and return a success message
    if auth_test:
        return jsonify({"interpersonal_test_result": "authentication_success"})

    try:
        content_type = request.headers["Content-type"]
    except KeyError:
        return json_error(400, "invalid_request", "No 'Content-type' header")

    request_body = {}
    request_files = {}
    if content_type == "application/json":
        request_body = json.loads(request.data)
    elif content_type == "application/x-www-form-urlencoded":
        request_body = request.form
    elif content_type.startswith("multipart/form-data"):
        request_body = request.form
        request_files = {f.filename: f for f in request.files.getlist("file")}
    else:
        return json_error(
            400, "invalid_request", f"Invalid 'Content-type': '{content_type}'"
        )

    request_file_names = [n for n in request_files.keys()]

    contype_test = request_body.get("interpersonal_content-type_test")
    # Check for the value we use in testing, and return a success message
    if contype_test:
        return jsonify(
            {
                "interpersonal_test_result": contype_test,
                "content_type": content_type,
                "filenames": request_file_names,
            }
        )

    # Per spec, missing 'action' should imply create
    action = request_body.get("action", "create")

    # Ahh yes, the famous CUUD.
    # These are all actions supported by the spec:
    # supported_actions = ["delete", "undelete", "update", "create"]
    supported_actions = ["create"]

    if action not in supported_actions:
        return json_error(400, "invalid_request", f"'{action}' action not supported")

    if action not in verified["scopes"]:
        return json_error(
            403, "insufficient_scope", f"Access token not valid for action '{action}'"
        )

    if action == "create":
        return json_error(400, "invalid_request", f"'delete' action not supported")
    else:
        return json_error(500, f"Unhandled action '{action}'")


@bp.route("/<blog_name>", methods=["GET", "POST"])
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


@bp.route("/<blog_name>/media")
@indieauth_required(ALL_HTTP_METHODS)
def micropub_blog_media(blog_name):
    """The per-blog media endpoint"""
    raise NotImplementedError