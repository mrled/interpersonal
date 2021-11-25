import base64
import datetime
import functools
import hashlib
import sqlite3
import typing

from cryptography.hazmat.primitives import constant_time
from flask import (
    current_app,
    g,
    redirect,
    request,
    url_for,
)

from interpersonal import database
from interpersonal.errors import (
    IndieauthCodeVerifierMismatchError,
    IndieauthInvalidGrantError,
    IndieauthMissingCodeVerifierError,
    InvalidAuthCodeError,
    InvalidBearerTokenError,
)


def indieauth_required(methods):
    """A decorator to indicate that IndieAuth login is required for a given route

    Can protect only some methods by passing methods=[...list...]

    WARNING: Decorator functions that take arguments, like this one does,
    must take only positional arguments!
    If there is a default value for the methods argument,
    Flask will give erros like:

        AssertionError: View function mapping is overwriting an existing endpoint function: indieauth.decorator

    An example of working code:
    <https://stackoverflow.com/questions/54032502/decorators-with-arguments-with-flask>
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_app.logger.debug(
                f"@indieauth_required({methods}) wraps urlfunc {func.__name__}. request.method: {request.method}; g.indieauthed: {g.indieauthed}."
            )
            if request.method in methods and not g.indieauthed:
                current_app.logger.debug(
                    f"Attempted to visit {request.url} without logging in; redirecting to login page first..."
                )
                return redirect(url_for("indieauth.login", next=request.url))
            return func(*args, **kwargs)

        return wrapper

    return decorator


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
            raise IndieauthMissingCodeVerifierError()

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
