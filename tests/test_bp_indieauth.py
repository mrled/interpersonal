"""Tests for the IndieAuth blueprint"""

import json
import secrets

import pytest
from flask import session
from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from interpersonal import database, util
from interpersonal.blueprints import indieauth
from tests.conftest import IndieAuthActions, TestConsts


def test_login(client, indieauthfix):
    assert client.get("/indieauth/login").status_code == 200
    response = indieauthfix.login()
    assert response.headers["Location"] == "http://localhost/indieauth/"

    with client:
        client.get("/")
        assert (
            session[indieauth.COOKIE_INDIE_AUTHED]
            == indieauth.COOKIE_INDIE_AUTHED_VALUE
        )


def test_logout(client, indieauthfix):
    assert client.get("/indieauth/login").status_code == 200
    login_response = indieauthfix.login()
    assert login_response.headers["Location"] == "http://localhost/indieauth/"

    with client:
        client.get("/")
        assert indieauth.COOKIE_INDIE_AUTHED in session
        assert (
            session[indieauth.COOKIE_INDIE_AUTHED]
            == indieauth.COOKIE_INDIE_AUTHED_VALUE
        )

        logout_response = indieauthfix.logout()
        assert indieauth.COOKIE_INDIE_AUTHED not in session


def test_authorize_GET(
    client: FlaskClient, indieauthfix: IndieAuthActions, testconstsfix: TestConsts
):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    authorize_uri = "/indieauth/authorize"

    indieauthfix.login()

    response_GET = client.get(
        util.uri(
            authorize_uri,
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redir_uri,
                "state": state,
                "code_challenge": None,
                "code_challenge_method": None,
                "me": testconstsfix.owner_profile,
                "scope": "profile",
            },
        )
    )

    try:
        assert response_GET.status_code == 200
        # Checking state is especially important, as it is used to prevent CSRF attacks
        assert state.encode() in response_GET.data
        assert client_id.encode() in response_GET.data
        assert redir_uri.encode() in response_GET.data
    except BaseException as exc:
        print("Failed GET tests!")
        print("Response body:")
        print(response_GET.data.decode())
        raise exc


def test_authorize_POST(
    client: FlaskClient, indieauthfix: IndieAuthActions, testconstsfix: TestConsts
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    authorize_uri = "/indieauth/authorize"

    indieauthfix.login()
    response_grant = indieauthfix.grant(
        client_id, redir_uri, "testing state", ["create"]
    )
    # response_grant.data will be something like:
    # b'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n<title>Redirecting...</title>\n<h1>Redirecting...</h1>\n<p>You should be redirected automatically to target URL: <a href="https://client.example.net/redir/to/here?code=kLHf5RxkuJTpGKd8ealmXA&amp;state=unrandom+state+for+just+this+test">https://client.example.net/redir/to/here?code=kLHf5RxkuJTpGKd8ealmXA&amp;state=unrandom+state+for+just+this+test</a>. If not click the link.'
    # We just need to extract the code from that
    authorization_code = (
        response_grant.data.decode().split("code=")[1].split("&amp;state=")[0]
    )

    # The POST method for this endpoint does not require cookies.
    # This because it is called by the IndieAuth client to verify permissions with the 'profile' scope.
    # It is not called by the user's browser and will not have the user's login cookies.
    # See also: <https://indieauth.spec.indieweb.org/#request>
    client.cookie_jar.clear()

    response_POST = client.post(
        authorize_uri,
        data={
            "code": authorization_code,
            "client_id": client_id,
            "redirect_uri": redir_uri,
            "code_challenge": None,
            "code_challenge_method": None,
        },
    )

    try:
        response_POST_json = json.loads(response_POST.data)
    except BaseException as exc:
        print("Could not JSON decode POST result")
        print("Response body:")
        print(response_POST.data.decode())
        raise exc

    try:
        assert response_POST.status_code == 200
        assert testconstsfix.owner_profile == response_POST_json["me"]
    except BaseException as exc:
        print("Failed POST tests!")
        print("Response body:")
        print(json.dumps(response_POST_json, indent=2, sort_keys=True))
        raise exc


def test_authorize_GET_requires_auth(client: FlaskClient, testconstsfix: TestConsts):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    authorize_uri = "/indieauth/authorize"

    response_GET = client.get(
        util.uri(
            authorize_uri,
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redir_uri,
                "state": state,
                "code_challenge": None,
                "code_challenge_method": None,
                "me": testconstsfix.owner_profile,
                "scope": "profile",
            },
        )
    )

    try:
        assert response_GET.status_code == 302
        # Checking state is especially important, as it is used to prevent CSRF attacks
        assert (
            b"You should be redirected automatically to target URL" in response_GET.data
        )
        assert b'<a href="/indieauth/login' in response_GET.data
    except BaseException as exc:
        print("Failed GET tests!")
        print("Response body:")
        print(response_GET.data.decode())
        raise exc

    # TODO: test that the authorization code doesn't show up in the database too


def test_grant(
    app: Flask,
    client: FlaskClient,
    indieauthfix: IndieAuthActions,
    testconstsfix: TestConsts,
):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    grant_uri = "/indieauth/grant"

    indieauthfix.login()

    response = client.post(
        grant_uri,
        data={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redir_uri,
            "state": state,
            "code_challenge": None,
            "code_challenge_method": None,
            "me": testconstsfix.owner_profile,
            "scope": "profile",
        },
    )

    authorization_code = (
        response.data.decode().split(f"{redir_uri}?code=")[1].split("&amp;")[0]
    )

    try:
        assert response.status_code == 302
        # All these strings will be in the response data because
        # the redirect returns an HTML page with the link, e.g.
        # https://client.example.net/redir/to/here?code=IRwCMEDMdpC-y_MX2xU4nA&amp;state=sZIdeWQYkCbpKZvG_qjEsA
        # Checking state is especially important, as it is used to prevent CSRF attacks
        assert state.encode() in response.data
        assert client_id.encode() in response.data
        assert redir_uri.encode() in response.data
    except BaseException as exc:
        print("Failed GET tests!")
        print("Response body:")
        print(response.data.decode())
        raise exc

    with app.app_context():
        db = database.get_db()
        row = db.execute(
            "SELECT authorizationCode, used, host, clientId, redirectUri, codeChallengeMethod, time FROM AuthorizationCode WHERE authorizationCode = ?",
            (authorization_code,),
        ).fetchone()
    assert row["authorizationCode"] == authorization_code
    assert row["used"] == 0


def test_redeem_auth_code(
    app: Flask, indieauthfix: IndieAuthActions, testconstsfix: TestConsts
):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    indieauthfix.login()
    grant_response = indieauthfix.grant(client_id, redir_uri, state, ["create"])
    authorization_code = indieauthfix.authorization_code_from_grant_response(
        grant_response, redir_uri
    )

    with app.app_context():
        db = database.get_db()
        row = db.execute(
            "SELECT authorizationCode, used, host, clientId, redirectUri, codeChallengeMethod, time FROM AuthorizationCode WHERE authorizationCode = ?",
            (authorization_code,),
        ).fetchone()

    assert row["authorizationCode"] == authorization_code
    assert row["used"] == 0

    # All of the above is just setup
    # Now we can actually test redeem_auth_code

    with app.app_context():
        redeemed = indieauth.redeem_auth_code(
            authorization_code, client_id, redir_uri, "localhost"
        )
        assert redeemed["authorizationCode"] == authorization_code
        assert redeemed["host"] == "localhost"
        assert redeemed["clientId"] == client_id
        assert redeemed["redirectUri"] == redir_uri
        assert redeemed["used"] == 1


def test_header(client: FlaskClient):
    """Spot checking that headers get applied to this blueprint

    Most checks are done in the root blueprint
    """
    response = client.get("/indieauth/login")
    assert (
        response.headers["Content-Security-Policy"]
        == "default-src 'none'; script-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    assert (
        response.headers["X-Interpersonal-Message"]
        == "Generated by Interpersonal, <https://github.com/mrled/interpersonal>"
    )


def test_bearer_GET_requires_auth(client: FlaskClient):
    response_GET = client.get("/indieauth/bearer")

    try:
        assert response_GET.status_code == 302
        assert b'<a href="/indieauth/login' in response_GET.data
    except BaseException as exc:
        print("Failed GET tests!")
        print("Response body:")
        print(response_GET.data.decode())
        raise exc


def test_bearer_GET_valid_token(
    client: FlaskClient, indieauthfix: IndieAuthActions, testconstsfix: TestConsts
):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    indieauthfix.login()
    grant_response = indieauthfix.grant(client_id, redir_uri, state, ["create"])
    authcode = indieauthfix.authorization_code_from_grant_response(
        grant_response, redir_uri
    )

    bearer_POST_response = indieauthfix.bearer(authcode, client_id, redir_uri)
    bearer_token = json.loads(bearer_POST_response.data)["access_token"]

    authheaders = Headers()
    authheaders["Authorization"] = f"Bearer {bearer_token}"
    verify_result = client.get("/indieauth/bearer", headers=authheaders)
    assert verify_result.status_code == 200
    assert client_id.encode() in verify_result.data
    assert testconstsfix.owner_profile.encode() in verify_result.data
    assert b'"scopes":["create"]' in verify_result.data


def test_bearer_verify_token(
    app: Flask, indieauthfix: IndieAuthActions, testconstsfix: TestConsts
):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    indieauthfix.login()
    grant_response = indieauthfix.grant(client_id, redir_uri, state, ["create"])
    authcode = indieauthfix.authorization_code_from_grant_response(
        grant_response, redir_uri
    )
    bearer_response = indieauthfix.bearer(authcode, client_id, redir_uri)
    bearer_data = json.loads(bearer_response.data)

    with app.app_context():
        valid_verify_result = indieauth.bearer_verify_token(
            bearer_data["access_token"],
        )
        assert valid_verify_result["client_id"] == client_id
        assert valid_verify_result["me"] == testconstsfix.owner_profile
        assert "create" in valid_verify_result["scopes"]

        with pytest.raises(indieauth.InvalidBearerTokenError):
            invalid_verify_result = indieauth.bearer_verify_token(
                "invalid-access-token-lol",
            )
            assert (
                b"Invalid bearer token 'invalid-access-token-lol'"
                in invalid_verify_result.data
            )


def test_bearer_POST_requires_auth(client: FlaskClient):
    resp1 = client.post(
        "/indieauth/bearer", data={"example": "data", "for": "thistest"}
    )
    try:
        assert resp1.status_code == 400
        assert b"Missing required form field 'code'" in resp1.data
    except BaseException as exc:
        print("Failed GET tests!")
        print("Response body:")
        print(resp1.data.decode())
        raise exc

    resp2 = client.post(
        "/indieauth/bearer",
        data={
            "code": "a very invalid one",
            "client_id": "invalidcid",
            "redirect_uri": "https://example.com",
            "host": "whatever",
        },
    )
    try:
        assert resp2.status_code == 401
        assert b"Invalid auth code 'a very invalid one'" in resp2.data
    except BaseException as exc:
        print("Failed GET tests!")
        print("Response body:")
        print(resp2.data.decode())
        raise exc


def test_bearer_POST(indieauthfix: IndieAuthActions, testconstsfix: TestConsts):

    ## Initial setup
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    ## Log in, grant, get auth code
    indieauthfix.login()
    grant_response = indieauthfix.grant(client_id, redir_uri, state, ["create"])
    authorization_code = indieauthfix.authorization_code_from_grant_response(
        grant_response, redir_uri
    )

    # Log out to make sure we aren't confusing indieauth authentication with bearer authentication
    indieauthfix.logout()

    ## POST that auth code to the bearer endpoint, exchanging it for an access token
    response = indieauthfix.bearer(authorization_code, client_id, redir_uri)

    # TODO: verify the database is in the state we expect too

    response_json = json.loads(response.data)

    assert response_json["me"] == testconstsfix.owner_profile
    assert response_json["scope"] == "create"
