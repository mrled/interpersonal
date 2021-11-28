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

from interpersonal.blueprints.indieauth.util import (
    VerifiedBearerToken,
    bearer_verify_token,
    indieauth_required,
)
from interpersonal.consts import ALL_HTTP_METHODS

from interpersonal.errors import (
    MicropubInsufficientScopeError,
    MicropubInvalidRequestError,
    MissingBearerAuthHeaderError,
    MissingBearerTokenError,
    catchall_error_handler,
    json_error,
)
from interpersonal.sitetypes.base import HugoBase


bp = Blueprint("micropub", __name__, url_prefix="/micropub", template_folder="temple")


bp.register_error_handler(Exception, catchall_error_handler)


@bp.route("/")
@indieauth_required(ALL_HTTP_METHODS)
def index():
    """The index page for the micropub blueprint

    Show a list of configured blogs
    """
    blogs = current_app.config["APPCONFIG"].blogs
    return render_template("micropub.index.html.j2", blogs=blogs)


def bearer_verify_token_from_auth_header(auth_header: str, me: str):
    """Given an Authorization header, verify the token.

    Return a VerifiedBearerToken.

    Raises exceptions if verification fails.
    """
    if not auth_header:
        raise MissingBearerAuthHeaderError()

    token = re.sub("Bearer ", "", auth_header)
    if not token:
        raise MissingBearerTokenError()

    verified = bearer_verify_token(token, me)
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
    blog = current_app.config["APPCONFIG"].blog(blog_name)

    verified = bearer_verify_token_from_auth_header(
        request.headers.get("Authorization"), blog.baseuri
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


def authenticate_POST(req: Request, blog: HugoBase) -> VerifiedBearerToken:
    """Authenticate a POST request

    POST requetss can be authenticated by either an auth token header or an
    auth token in the submitted form.
    """
    current_app.logger.debug(f"authenticate_POST: all headers: {req.headers}")
    form_encoded = req.headers.get("Content-type") in [
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]
    form_auth_token = req.form.get("auth_token")
    if form_encoded and form_auth_token:
        current_app.logger.debug(f"authenticate_POST(): Using auth_token from form...")
        verified = bearer_verify_token(form_auth_token, blog.baseuri)
    else:
        current_app.logger.debug(f"authenticate_POST(): Using Authorization header...")
        verified = bearer_verify_token_from_auth_header(
            req.headers.get("Authorization"), blog.baseuri
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


def form_body_to_mf2_json(request_body: typing.Dict):
    """Given a request body from a form, return microformats2 json"""

    # Keys in this list are part of our application, not mf2 json, so we ignore them
    ignored_keys = ["auth_token", "action"]

    result = {
        "type": ["h-entry"],
        "properties": {},
    }
    for k in request_body:

        # Note that v is now a list, possibly of just a single item, not a scalar
        # Note that mf2 uses lists for many things, so this is actually fine
        v = request_body.getlist(k)

        if k in ignored_keys:
            continue
        elif k == "h":
            result["type"] = v
        elif k.endswith("[]"):
            # Form convention is that a list is made like this:
            # ?tag[]=tag1&tag[]=tag2
            # Handle that here
            propname = k[0:-2]
            if propname not in result["properties"]:
                result["properties"][propname] = v
        else:
            result["properties"][k] = v

    return result


@bp.route("/<blog_name>", methods=["POST"])
def micropub_blog_endpoint_POST(blog_name: str):
    """The POST verb for the micropub blog route

    Used by clients to change content (CRUD operations on posts)
    """
    blog = current_app.config["APPCONFIG"].blog(blog_name)

    current_app.logger.debug(
        f"/{blog_name}: all headers before calling authentiate_POST: {request.headers}"
    )
    verified = authenticate_POST(request, blog)

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

        if content_type == "application/json":
            mf2obj = request_body
        elif (
            content_type == "application/x-www-form-urlencoded"
            or content_type.startswith("multipart/form-data")
        ):
            mf2obj = form_body_to_mf2_json(request_body)
        else:
            raise MicropubInvalidRequestError(
                f"Unhandled 'Content-type': '{content_type}'"
            )

        new_post_location = blog.add_post_mf2(mf2obj)
        resp = Response("")
        resp.headers["Location"] = new_post_location
        resp.status_code = 201

        return resp

    else:
        return json_error(500, f"Unhandled action '{action}'")


@bp.route("/<blog_name>/media")
@indieauth_required(ALL_HTTP_METHODS)
def micropub_blog_media(blog_name):
    """The per-blog media endpoint"""
    raise NotImplementedError


@bp.route("/authorized/github")
def micropub_authorized():
    """Redirection destination when installing an oauth app on a third party service

    E.g. when installing Interpersonal as a Github app,
    you should be redirected here when the app is successfully installed.

    See /docs/github-app.md for more examples.

    If more site types are added, code here may need to change.
    E.g. if we started to support Gitlab site types.
    """

    code = request.form.get("code")
    installation_id = request.form.get("installation_id")
    setup_action = request.form.get("setup_action")

    blogs = current_app.config["APPCONFIG"].blogs

    return render_template(
        "micropub.authorized.html.j2",
        installed_to="GitHub",
        code=code,
        installation_id=installation_id,
        setup_action=setup_action,
    )
