"""Blueprint for a micropub endpoint implementation.

Kept separate from indieauth, but note that it must know of the indieauth token
endpoint in advance, so there is some coupling.
"""

import datetime
import json
import re
import typing

from flask import (
    Blueprint,
    Request,
    current_app,
    jsonify,
    render_template,
    request,
    url_for,
)
from flask.wrappers import Response

from interpersonal import util
from interpersonal.blueprints.indieauth import (
    ALL_HTTP_METHODS,
    VerifiedBearerToken,
    bearer_verify_token,
    indieauth_required,
)

#### WARNING!!! Make sure to register the error handler on each of these!
from interpersonal.errors import (
    MicropubBlogNotFoundError,
    MicropubInsufficientScopeError,
    MicropubInvalidRequestError,
    MissingBearerAuthHeaderError,
    MissingBearerTokenError,
    InvalidBearerTokenError,
    render_error,
    json_error,
)
from interpersonal.sitetypes.base import HugoBase


bp = Blueprint("micropub", __name__, url_prefix="/micropub")

for err in [
    MicropubBlogNotFoundError,
    MicropubInsufficientScopeError,
    MicropubInvalidRequestError,
    MissingBearerAuthHeaderError,
    MissingBearerTokenError,
    InvalidBearerTokenError,
]:
    bp.register_error_handler(err, err.handler)


def blog_from_blog_name(blog_name: str) -> HugoBase:
    """Given a blog name, find a configured blog in the list"""
    try:
        return current_app.config["APPCONFIG"].blog(blog_name)
    except KeyError:
        raise MicropubBlogNotFoundError(blog_name)


@bp.route("/")
@indieauth_required(ALL_HTTP_METHODS)
def index():
    """The index page for the micropub blueprint

    Show a list of configured blogs
    """
    blogs = current_app.config["APPCONFIG"].blogs
    return render_template("micropub/index.html.j2", blogs=blogs)


def bearer_verify_token_from_auth_header(auth_header: str):
    """Given an Authorization header, verify the token.

    Return a VerifiedBearerToken.

    Raises exceptions if verification fails.
    """
    if not auth_header:
        raise MissingBearerAuthHeaderError()

    token = re.sub("Bearer ", "", auth_header)
    if not token:
        raise MissingBearerTokenError()

    verified = bearer_verify_token(token)
    current_app.logger.debug(
        f"Successfully verified token {token} for owner {verified['me']} using client {verified['client_id']} authorized for scope {verified['scopes']}"
    )

    return verified


@bp.route("/<blog_name>", methods=["GET"])
def micropub_blog_endpoint_GET(blog_name: str):
    """The GET verb for the micropub blog route

    Used by clients to:
    * Retrieve the configuration, including the media-endpoint and any syndication targets
      (syndication targets currently not supported)
    * Retrieve metadata for a given URL, such as published date and tags, in microformats2-json format
    """
    blog = blog_from_blog_name(blog_name)

    verified = bearer_verify_token_from_auth_header(
        request.headers.get("Authorization")
    )

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
            raise MicropubInvalidRequestError("Required 'url' parameter missing")
        try:
            post = blog.get_post(url)
            return jsonify(post.mf2json)
        # TODO: Raise a specific error in the blog object when a post is not found
        except KeyError:
            return json_error(404, "no such blog post")

    elif q == "syndicate-to":
        raise MicropubInvalidRequestError("syndication is not implemented")

    else:
        raise MicropubInvalidRequestError(
            "Valid authorization, but invalid or missing 'q' parameter"
        )


def authenticate_POST(req: Request) -> VerifiedBearerToken:
    """Authenticate a POST request

    POST requetss can be authenticated by either an auth token header or an
    auth token in the submitted form.
    """
    form_encoded = req.headers.get("Content-type") in [
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]
    form_auth_token = req.form.get("auth_token")
    if form_encoded and form_auth_token:
        verified = bearer_verify_token(form_auth_token)
    else:
        verified = bearer_verify_token_from_auth_header(
            req.headers.get("Authorization")
        )
    return verified


def process_POST_body(
    req: Request, content_type: str
) -> typing.Tuple[typing.Dict, typing.Dict]:
    """Process a POST request body and return a tuple of the body and files

    Manage a POST body whether it is in JSON format or a form
    """
    request_body = {}
    request_files = {}
    if content_type == "application/json":
        request_body = json.loads(req.data)
    elif content_type == "application/x-www-form-urlencoded":
        request_body = req.form
    elif content_type.startswith("multipart/form-data"):
        request_body = req.form
        request_files = {f.filename: f for f in req.files.getlist("file")}
    else:
        raise MicropubInvalidRequestError(f"Invalid 'Content-type': '{content_type}'")
    return (request_body, request_files)


def new_post_from_request(request_body: typing.Dict, blog: HugoBase):
    """Instruct the blog to create a new post

    request_body:   Dict from a parsed and normalized request body
    blog:           The blog to create the post on
    """
    frontmatter = {}
    content = ""
    slug = ""
    content_type = ""
    # TODO: add test for urlencoded body where k ends with [] to indicate an array
    # e.g. ?tag[]=hacking&tag[]=golang should end up with both 'hacking' and 'golang' tags
    for k, v in request_body.items():
        if k == "h":
            content_type = v
        elif k == "content":
            content = v
        elif k == "slug":
            slug = v
        else:
            frontmatter[k] = v
    if not slug:
        raise MicropubInvalidRequestError("Missing 'slug'")
    if not content:
        raise MicropubInvalidRequestError("Missing 'content'")
    if not content_type:
        raise MicropubInvalidRequestError("Missing 'h'")
    if "date" not in frontmatter:
        frontmatter["date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    new_post_location = blog.add_post(slug, frontmatter, content)
    resp = Response("")
    resp.headers["Location"] = new_post_location
    return resp


@bp.route("/<blog_name>", methods=["POST"])
def micropub_blog_endpoint_POST(blog_name: str):
    """The POST verb for the micropub blog route

    Used by clients to change content (CRUD operations on posts)
    """
    blog = blog_from_blog_name(blog_name)
    verified = authenticate_POST(request)

    auth_test = request.headers.get("X-Interpersonal-Auth-Test")
    # Check for the header we use in testing, and return a success message
    if auth_test:
        return jsonify({"interpersonal_test_result": "authentication_success"})

    content_type = request.headers.get("Content-type")
    if not content_type:
        raise MicropubInvalidRequestError("No 'Content-type' header")

    request_body, request_files = process_POST_body(request, content_type)
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
    # But I don't support them all right now:
    supported_actions = ["create"]

    if action not in verified["scopes"]:
        raise MicropubInsufficientScopeError(action)

    if action not in supported_actions:
        raise MicropubInvalidRequestError(f"'{action}' action not supported")
    actest = request_body.get("interpersonal_action_test")
    if actest:
        return jsonify({"interpersonal_test_result": actest, "action": action})

    if action == "create":
        return new_post_from_request(request_body, blog)
    else:
        return json_error(500, f"Unhandled action '{action}'")


@bp.route("/<blog_name>/media")
@indieauth_required(ALL_HTTP_METHODS)
def micropub_blog_media(blog_name):
    """The per-blog media endpoint"""
    raise NotImplementedError
