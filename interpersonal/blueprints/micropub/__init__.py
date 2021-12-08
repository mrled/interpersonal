"""Blueprint for a micropub endpoint implementation.

Kept separate from indieauth, but note that it must know of the indieauth token
endpoint in advance, so there is some coupling.
"""

import json
import os.path
import re
import typing
from urllib.parse import unquote

from flask import (
    Blueprint,
    Request,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask.wrappers import Response
from werkzeug.datastructures import Headers

from interpersonal.blueprints.indieauth.util import (
    VerifiedBearerToken,
    bearer_verify_token,
    indieauth_required,
)
from interpersonal.consts import ALL_HTTP_METHODS

from interpersonal.errors import (
    AuthenticationProvidedTwiceError,
    MicropubInsufficientScopeError,
    MicropubInvalidRequestError,
    MissingBearerAuthHeaderError,
    MissingBearerTokenError,
    catchall_error_handler,
    json_error,
)
from interpersonal.sitetypes.base import HugoBase
from interpersonal.util import listflatten


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


def authenticate_POST(
    req_headers: Headers, processed_req_body: typing.Dict, blog: HugoBase
) -> VerifiedBearerToken:
    """Authenticate a POST request

    req_headers:            The Headaers from the request.
    processed_req_body:     The processed body from the request.
                            Normalized body whether this is a form or JSON request.
    blog:                   The blog for this request.

    POST requetss can be authenticated by either an auth token header or an
    auth token in the submitted form.

    TODO: Match OAuth Bearer Token RFC more closely
        Look for "access_token" in this document
        <https://datatracker.ietf.org/doc/html/rfc6750>
        Note that per the Micropub spec
        <https://www.w3.org/TR/micropub/#h-authentication-1>,
        "Micropub requests MUST be authenticated by including a Bearer Token in either the HTTP header or a form-encoded body parameter as described in the OAuth Bearer Token RFC."
        That RFC is constrained more than we are here, should fix.
    """
    current_app.logger.debug(f"authenticate_POST: all headers: {req_headers}")
    content_type = req_headers.get("Content-type")
    form_encoded = (
        content_type == "application/x-www-form-urlencoded"
        or content_type.startswith("multipart/form-data")
    )
    body_access_token = processed_req_body.get("access_token")

    if req_headers.get("Authorization") and body_access_token:
        raise AuthenticationProvidedTwiceError
    elif form_encoded and body_access_token:
        current_app.logger.debug(
            f"authenticate_POST(): Using access_token from form..."
        )
        verified = bearer_verify_token(body_access_token, blog.baseuri)
    else:
        current_app.logger.debug(f"authenticate_POST(): Using Authorization header...")
        verified = bearer_verify_token_from_auth_header(
            req_headers.get("Authorization"), blog.baseuri
        )
    return verified


def listflatten(lists) -> typing.List:
    """Given a list of lists, return a flattened single list"""
    return [val for sublist in lists for val in sublist]


def process_POST_body(
    req: Request, content_type: str
) -> typing.Tuple[typing.Dict, typing.Dict]:
    """Process a POST request body and return a tuple of the body and files

    Manage a POST body whether it is in JSON format or a form

    WARNING: This function is called BEFORE the request is authenticated!
    """
    request_body = {}
    request_files = {}
    if content_type == "application/json":
        request_body = json.loads(req.data)
    elif content_type == "application/x-www-form-urlencoded":
        request_body = req.form
    elif content_type.startswith("multipart/form-data"):
        request_body = req.form
        # Files uploaded in a multipart form MIGHT have a filename but WILL have a name.
        # The filename is optional and self-explanatory.
        # The name is the name of the form element that it was uploaded for,
        # and is the key for the MultiDict in req.files.
        # Micropub expects 'photo', 'video', and 'audio', but no other names.
        # There may be multiple files uploaded with the same name attribute,
        # if the <input> element in the HTML form allowed multiple selection.
        # See /docs/media.md for more details.
        request_files["photo"] = req.files.getlist("photo")
        request_files["video"] = req.files.getlist("video")
        request_files["audio"] = req.files.getlist("audio")
    else:
        raise MicropubInvalidRequestError(f"Invalid 'Content-type': '{content_type}'")
    return (request_body, request_files)


def form_body_to_mf2_json(request_body: typing.Dict):
    """Given a request body from a form, return microformats2 json"""

    def is_reserved(key):
        """Return True if form element is reserved by Interpersonal or Micropub

        <https://www.w3.org/TR/micropub/#h-reserved-properties>

        "When creating posts using x-www-form-urlencoded or multipart/form-data requests, all other properties in the request are considered properties of the object being created."
        """
        # Micropub requires 'access_token', but I had 'auth_token' erroneously at first
        reserved_keys = ["auth_token", "access_token", "action", "h", "url"]
        reserved_prefixes = ["mp-"]
        if key in reserved_keys:
            return True
        for prefix in reserved_prefixes:
            if key.startswith(prefix):
                return True
        return False

    result = {
        "type": ["h-entry"],
        "properties": {},
    }
    for key in request_body:

        # val is a list, possibly of just a single item, not a scalar.
        # mf2 uses lists for many things, even that will just have a single value
        # like the post name, so this is actually fine.
        # Form convention is that a list is made like this: ?tag[]=tag1&tag[]=tag2,
        # and Request.form.getlist(key) turns those into a single tag with two elements.
        val = [unquote(v) for v in request_body.getlist(key)]

        if is_reserved(key):
            continue
        elif key == "h":
            result["type"] = val
        elif key.endswith("[]"):
            # If a key ends with [], strip it off.
            # As previously mentioned, this is the convention for list items in a form.
            propname = key[0:-2]
            result["properties"][propname] = val
        else:
            result["properties"][key] = val

    return result


@bp.route("/<blog_name>", methods=["POST"])
def micropub_blog_endpoint_POST(blog_name: str):
    """The POST verb for the micropub blog route

    Used by clients to change content (CRUD operations on posts)

    If this is a multipart/form-data request,
    note that the multiple media items can be uploaded in one request,
    and they should be sent with a `name` of either `photo`, `video`, or `audio`.
    (multipart/form-data POST requests can send more than one attachment with the same `name`.)
    This is in contrast to the media endpoint,
    which expects a single item with a `name` of simply `file`.
    """
    blog: HugoBase = current_app.config["APPCONFIG"].blog(blog_name)

    content_type = request.headers.get("Content-type")
    if not content_type:
        raise MicropubInvalidRequestError("No 'Content-type' header")
    request_body, request_files = process_POST_body(request, content_type)

    current_app.logger.debug(
        f"/{blog_name}: all headers before calling authentiate_POST: {request.headers}"
    )
    verified = authenticate_POST(request.headers, request_body, blog)

    auth_test = request.headers.get("X-Interpersonal-Auth-Test")
    # Check for the header we use in testing, and return a success message
    if auth_test:
        return jsonify({"interpersonal_test_result": "authentication_success"})

    contype_test = request_body.get("interpersonal_content-type_test")
    # Check for the value we use in testing, and return a success message
    if contype_test:
        return jsonify(
            {
                "interpersonal_test_result": contype_test,
                "content_type": content_type,
                "uploaded_file_count": len(listflatten(request_files.values())),
            }
        )

    # Per spec, missing 'action' should imply create
    action = request_body.get("action", "create")

    # Ahh yes, the famous CUUD.
    # These are all actions supported by the spec:
    # supported_actions = ["delete", "undelete", "update", "create"]
    # But I don't support them all right now.
    # TODO: Support delete, undelete, and update actions
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
        elif content_type == "application/x-www-form-urlencoded":
            mf2obj = form_body_to_mf2_json(request_body)
        elif content_type.startswith("multipart/form-data"):

            mf2obj = form_body_to_mf2_json(request_body)

            # Multipart forms contain attachments.
            # Upload the attachments, then append the URIs to the mf2 object.
            # We want to append, not replace, the attachments -
            # if the post includes a photo URI and also some photo uploads,
            # we need to keep both.
            # (Not sure if that actually happens out in the wild, but maybe?)
            # mtype will be one of 'photo', 'video', 'audio'.
            for mtype in request_files:
                mitems = request_files[mtype]
                added = blog.add_media(mitems)
                if mtype not in mf2obj["properties"]:
                    mf2obj["properties"][mtype] = []
                mf2obj["properties"][mtype] += [a.uri for a in added]

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


@bp.route("/<blog_name>/media", methods=["POST"])
def micropub_blog_media(blog_name):
    """The per-blog media endpoint

    Expects a multipart/form-data request with a single attachment with a name of `file`.
    Contrast with a multipart/form-data requiest of the main POST endpoint,
    which accepts attachments with a name of `photo`, `video`, or `audio`.
    """
    blog: HugoBase = current_app.config["APPCONFIG"].blog(blog_name)

    content_type = request.headers.get("Content-type")
    if not content_type:
        raise MicropubInvalidRequestError("No 'Content-type' header")
    if not content_type.startswith("multipart/form-data"):
        raise MicropubInvalidRequestError(
            f"Invalid Content-type: {content_type}; only 'multipart/form-data' is supported for this endpoint."
        )

    verified = authenticate_POST(request.headers, request.form, blog)
    if "media" not in verified["scopes"]:
        raise MicropubInsufficientScopeError("media")

    files = request.files.getlist("file")
    if len(files) != 1:
        raise MicropubInvalidRequestError(
            f"Exactly one file can be submitted at a time, but this request has {len(files)} files"
        )
    added = blog.add_media(files)[0]
    resp = Response("")
    resp.headers["Location"] = added.uri
    resp.status_code = 201 if added.created else 200
    return resp


@bp.route("/<blog_name>/staging/<path:path>", methods=["GET"])
def micropub_blog_staging(blog_name, path):
    """The per-blog temporary media staging endpoint

    Blogs can be configured to save media here temporarily until a post is created.
    """
    blog_media_staging = os.path.join(current_app.config["MEDIASTAGING"], blog_name)
    return send_from_directory(blog_media_staging, path)


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
