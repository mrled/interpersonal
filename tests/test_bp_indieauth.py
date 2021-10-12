"""Tests for the IndieAuth blueprint"""

import json
import secrets

from flask import session
from flask.cli import with_appcontext

from interpersonal import database, util
from interpersonal.blueprints import indieauth


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


def test_authorize_GET(client, indieauthfix, testconstsfix):
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


def test_authorize_POST(client, indieauthfix, testconstsfix):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    authorize_uri = "/indieauth/authorize"

    indieauthfix.login()
    response_grant = indieauthfix.grant(client_id, redir_uri)
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


def test_authorize_GET_requires_auth(client, indieauthfix, testconstsfix):
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


def test_grant(app, client, indieauthfix, testconstsfix):
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


def test_redeem_auth_code(app, client, indieauthfix, testconstsfix):
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
