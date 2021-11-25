import base64
import datetime
import hashlib
import re
import secrets
import sqlite3
import typing
from urllib.parse import unquote

import rfc3986
from cryptography.hazmat.primitives import constant_time
from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from interpersonal import database
from interpersonal.consts import (
    ALL_HTTP_METHODS,
    SCOPE_INFO,
)
from interpersonal.blueprints.indieauth.util import indieauth_required
from interpersonal.util import uri_copy_and_append_query

from interpersonal.errors import (
    IndieauthCodeVerifierMismatchError,
    IndieauthInvalidGrantError,
    InvalidAuthCodeError,
    InvalidBearerTokenError,
    render_error,
    catchall_error_handler,
)


COOKIE_INDIE_AUTHED = "indie_authed"
COOKIE_INDIE_AUTHED_VALUE = "indied (indeed) (lol)"


bp = Blueprint("indieauth", __name__, url_prefix="/indieauth", template_folder="temple")


bp.register_error_handler(Exception, catchall_error_handler)


@bp.before_app_request
def load_logged_in_user():
    """Determine whether user is logged in before any view function runs

    It is safe to do this in the cookie, because we are using encrypted cookies.
    """
    g.indieauthed = session.get(COOKIE_INDIE_AUTHED) is not None


@bp.route("/")
def index():
    return render_template("indieauth.index.html.j2")


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Return the log in page"""
    if request.method == "POST":
        form_login_password = request.form.get("password", None)

        if form_login_password is None:
            error = "No password passed to form"

        else:
            config_login_password = current_app.config["APPCONFIG"].password
            if form_login_password != config_login_password:
                error = f"Incorrect login token '{form_login_password}'"
            else:
                session.clear()
                session[COOKIE_INDIE_AUTHED] = COOKIE_INDIE_AUTHED_VALUE
                target = request.args.get("next", url_for("indieauth.index"))
                current_app.logger.debug(f"Login successful, will redirect to {target}")
                return redirect(target)

        flash(error)

    return render_template("indieauth.login.html.j2")


@bp.route("/logout")
def logout():
    """Log the user out immediately"""
    session.clear()
    return redirect(url_for("indieauth.index"))


@bp.route("/authorize", methods=["GET"])
@indieauth_required(["GET"])
def authorize_GET():
    """The GET handler for the IndieAuth authorization endpoint

    <https://indieauth.spec.indieweb.org/#authorization-request>

    response_type=code - Indicates to the authorization server that an authorization code should be returned as the response
    client_id - The client URL
    redirect_uri - The redirect URL indicating where the user should be redirected to after approving the request
    state - A parameter set by the client which will be included when the user is redirected back to the client. This is used to prevent CSRF attacks. The authorization server MUST return the unmodified state value back to the client.
    code_challenge - The code challenge as previously described.
    code_challenge_method - The hashing method used to calculate the code challenge, e.g. "S256"
    scope - (optional) A space-separated list of scopes the client is requesting, e.g. "profile", or "profile create". If the client omits this value, the authorization server MUST NOT issue an access token for this authorization code. Only the user's profile URL may be returned without any scope requested. See Profile Information for details about which scopes to request to return user profile information.
    me - (optional) The URL that the user entered
    """

    client_id = request.args.get("client_id")
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state")
    response_type = request.args.get("response_type", "code")
    code_challenge = request.args.get("code_challenge")
    code_challenge_method = request.args.get("code_challenge_method")
    scope = request.args.get("scope", "profile")
    me = request.args.get("me")

    current_app.logger.debug(
        f"client_id, redirect_uri, state: {client_id}, {redirect_uri}, {state}"
    )

    if not all([client_id, redirect_uri, state]):
        return render_error(
            400, f"Missing at least one of client_id, redirect_uri, state"
        )
    if response_type != "code":
        return render_error(400, "Parameter response_type must be 'code'")

    parsed_client_id = rfc3986.uri_reference(client_id).normalize()
    if not parsed_client_id.is_valid(require_scheme=True, require_authority=True):
        return render_error(
            400, f"client_id parameter '{client_id}' is not a valid URI"
        )

    parsed_redirect_uri = rfc3986.uri_reference(redirect_uri).normalize()
    if not parsed_redirect_uri.is_valid(require_scheme=True, require_authority=True):
        return render_error(
            400, f"redirect_uri parameter '{redirect_uri}' is not a valid URI"
        )

    if (
        parsed_client_id.scheme != parsed_redirect_uri.scheme
        or parsed_client_id.authority != parsed_redirect_uri.authority
    ):
        return render_error(400, f"redirect_uri must be on the same host as client_id")

    return render_template(
        "indieauth.authorize.html.j2",
        scope_info=SCOPE_INFO,
        response_type=response_type,
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        requested_scope_list=scope.split(),
        me=me,
    )


@bp.route("/authorize", methods=["POST"])
def authorize_POST():
    """The POST verb for the IndieAuth authorization endpoint

    Note that the GET method requires authorization,
    but the POST method is used by an IndieAuth client and thus authorization is not required.

    <https://indieauth.spec.indieweb.org/#request>

    > If the client only needs to know the user who logged in and does not need to make requests to resource servers with an access token, the client exchanges the authorization code for the user's profile URL at the authorization endpoint.

    (By contrast, micropub clients which DO need to make requests to resource servers with an access token use the "token endpoint")

    code - An authorization_code generated from the /grant endpoint
    client_id - The client URL
    redirect_uri - The redirect URL indicating where the user should be redirected to after approving the request
    """
    authorization_code = request.form["code"]
    origin_host = request.headers["Host"]
    client_id = request.form["client_id"]
    redirect_uri = request.form["redirect_uri"]
    code_challenge = request.form.get("code_challenge")
    code_challenge_method = request.form.get("code_challenge_method")
    code_verifier = request.form.get("code_verifier")

    redeem_auth_code(
        authorization_code, client_id, redirect_uri, origin_host, code_verifier
    )
    return jsonify(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "me": current_app.config["APPCONFIG"].owner_profile,
        }
    )


@bp.route("/grant", methods=["POST"])
@indieauth_required(ALL_HTTP_METHODS)
def grant():
    """Grant permission to another site with IndieAuth

    Once the user authenticates and allows access to the app,
    the browser is redirected to this endpoint
    which records the authorization in the database
    and redirects the user to their final destination.
    """
    if request.headers.get("sec-fetch-site", "same-origin") != "same-origin":
        return render_error(401, "Request must be same origin")

    client_id = unquote(request.form.get("client_id"))
    redirect_uri = unquote(request.form.get("redirect_uri"))
    state = request.form.get("state")
    code_challenge = request.form.get("code_challenge")
    code_challenge_method = request.form.get("code_challenge_method")

    if not client_id or not redirect_uri or not state:
        return render_error(400, "Must pass all of client_id, redirect_uri, state")

    scopes = [s for s in SCOPE_INFO.keys() if request.form.get("scope:" + s) == "on"]
    current_app.logger.debug(
        f"In grant(). SCOPE_INFO.keys(): {SCOPE_INFO.keys()} Form: {request.form}. Enabled scopes: {scopes}"
    )
    authorization_code = secrets.token_urlsafe(16)

    # Described here
    # <https://indieauth.spec.indieweb.org/#authorization-response>
    # Note that the URI is defined by the client,
    # but we have to append code= and state= parameters.
    redir_dest = uri_copy_and_append_query(
        redirect_uri,
        {
            "code": authorization_code,  # We call this 'code' here because that's what OAuth 2.0 calls it
            "state": state,
        },
    )

    db = database.get_db()
    db.execute(
        database.INSERT_AUTHORIZATION_CODE_SQL,
        (
            authorization_code,
            datetime.datetime.utcnow(),
            client_id,
            redirect_uri,
            state,
            code_challenge or "",
            code_challenge_method or "",
            " ".join(scopes),
            request.headers["host"],
        ),
    )
    db.commit()

    current_app.logger.debug(
        f"Finished grant() function, redirecting to {redir_dest}..."
    )

    return redirect(redir_dest, 302)


def redeem_auth_code(
    authorization_code: str,
    client_id: str,
    redirect_uri: str,
    origin_host: str,
    code_verifier: str = "",
) -> sqlite3.Row:
    """Use an auth code

    Marks the code used and returns a new bearer token.

    Parameters

        code: An authorization code. This must be a code of type 'authorization_code', not like something else, TODO idk what else it could be tho.
        client_id: ID of the client app (should be a URI)
        redirect_uri: Redirect here after redeeming the code
        origin_host: The origin host, retrieved from the Host header of the HTTP request
        code_verifier: Required for the S256 code challenge method
    """
    db = database.get_db()
    row = db.execute(
        "SELECT used, host, clientId, redirectUri, codeChallenge, codeChallengeMethod, time FROM AuthorizationCode WHERE authorizationCode = ?",
        (authorization_code,),
    ).fetchone()
    if not row:
        raise InvalidAuthCodeError(authorization_code)

    if (
        datetime.datetime.utcnow() - row["time"] > datetime.timedelta(minutes=5)
        or client_id != row["clientId"]
        or redirect_uri != row["redirectUri"]
        or row["used"]
        or row["host"] != origin_host
    ):
        raise IndieauthInvalidGrantError

    if row["codeChallengeMethod"] == "S256":
        if not code_verifier:
            return render_error(400, "Missing code_verifier for S256")

        # You can add the == padding even if it is not necessary
        # <https://stackoverflow.com/a/49459036>
        # TODO: Test this code
        # I don't understand the codeChallenge stuff, so I don't test it yet.
        decoded_code_challenge = base64.urlsafe_b64decode(row["codeChallenge"] + "==")
        if not constant_time.bytes_eq(
            hashlib.sha256(code_verifier.encode()).digest(),
            decoded_code_challenge,
        ):
            raise IndieauthCodeVerifierMismatchError

    db.execute(
        "UPDATE AuthorizationCode SET used = 1 WHERE authorizationCode = ?",
        (authorization_code,),
    )
    db.commit()

    # Get the same row back from the database again
    # This means it'll pick up the change we made - setting it to used
    # which is useful in testing
    finalrow = db.execute(
        "SELECT authorizationCode, time, clientId, redirectUri, codeChallenge, codeChallengeMethod, scopes, host, used FROM AuthorizationCode WHERE authorizationCode = ?",
        (authorization_code,),
    ).fetchone()

    return finalrow


class VerifiedBearerToken(typing.TypedDict):
    me: str
    client_id: str
    scopes: typing.List[str]


def bearer_verify_token(token: str) -> VerifiedBearerToken:
    """Verify a bearer token"""
    db = database.get_db()
    row = db.execute(
        """
            SELECT
                bearerToken,
                clientId,
                scopes
            FROM
                BearerToken
            WHERE
                bearerToken = ?;
        """,
        (token,),
    ).fetchone()
    if not row:
        raise InvalidBearerTokenError(token)
    current_app.logger.debug(f"Found valid bearer token: {row}")

    return {
        "me": current_app.config["APPCONFIG"].owner_profile,
        "client_id": row["clientId"],
        "scopes": row["scopes"].split(" "),
    }


@bp.route("/bearer", methods=["GET"])
@indieauth_required(["GET"])
def bearer_GET():
    """Handle a GET request for the bearer endpoint

    GET requests are used to verify a token that the client has.

    <https://indieweb.org/token-endpoint#Verifying_an_Access_Token>
    """
    authh = request.headers["Authorization"]
    token = re.sub("^Bearer ", "", authh)
    return jsonify(bearer_verify_token(token))


@bp.route("/bearer", methods=["POST"])
def bearer_POST():
    """Handle a POST request for the bearer endpoint.

    After the user authorizes the client via the authorization endpoint,
    the client exchanges the authorization code it got
    for an access token by making a POST request to the bearer endpoint,
    which is managed in this function.

    <https://indieweb.org/token-endpoint#Granting_an_Access_Token>
    """

    current_app.logger.debug(f"bearer_POST(): request.form: {request.form}")

    db = database.get_db()

    action = request.form.get("action")

    if action == "revoke":
        token = request.form["token"]
        tokRow = db.execute(
            "SELECT host from BearerToken WHERE token = ?", (token,)
        ).fetchone()
        if tokRow["host"] == request.headers["host"]:
            db.execute("UPDATE BearerToken SET revoked 1 WHERE token = ?;", (token,))
        return

    elif action and action != "create":
        return render_error(400, f"Invalid action {action}")

    # If an action is not specified, assume "create"

    ## TODO: make sure the 'me' property is one we actually authorize for

    try:
        code = request.form["code"]
        client_id = request.form["client_id"]
        redirect_uri = request.form["redirect_uri"]
        host = request.headers["host"]
        code_verifier = request.form.get("code_verifier")
    except KeyError as exc:
        return render_error(400, f"Missing required form field '{exc.args[0]}'")
    code_row = redeem_auth_code(code, client_id, redirect_uri, host, code_verifier)

    bearer_token = secrets.token_urlsafe(16)

    db.execute(
        database.INSERT_BEARER_TOKEN_SQL,
        (
            bearer_token,
            datetime.datetime.utcnow(),
            code_row["authorizationCode"],
            code_row["clientId"],
            code_row["scopes"],
            request.headers["host"],
        ),
    )
    db.commit()

    response = {
        "me": request.form["me"],
        "token_type": "bearer",
        "access_token": bearer_token,
        "scope": code_row["scopes"],
    }
    return jsonify(response)
