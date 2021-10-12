"""Tests for the IndieAuth blueprint"""

import json
import re
import secrets

from flask import session

from interpersonal import util
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

    # TODO: test that the code gets recorded in the database properly


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


def test_grant(client, indieauthfix, testconstsfix):
    state = secrets.token_urlsafe(16)
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    authorize_uri = "/indieauth/grant"

    indieauthfix.login()

    response = client.post(
        authorize_uri,
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

    # assert response_GET.status_code == 200
    # # Checking state is especially important, as it is used to prevent CSRF attacks
    # assert state.encode() in response_GET.data
    # assert client_id.encode() in response_GET.data
    # assert redir_uri.encode() in response_GET.data

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
