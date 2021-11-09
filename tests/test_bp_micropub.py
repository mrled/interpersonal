"""Tests for the micropub blueprint"""

import json

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions


def test_index_requires_auth(client: FlaskClient):
    response = client.get("/micropub/")

    try:
        assert response.status_code == 302
        assert b'<a href="/indieauth/login' in response.data
    except BaseException as exc:
        print("/micropub/ index endpoint should require authentication")
        print("Response body:")
        print(response.data.decode())
        raise exc


def test_index_with_auth_shows_blog_list(
    client: FlaskClient, indieauthfix: IndieAuthActions
):
    indieauthfix.login()

    response = client.get("/micropub/")

    try:
        assert response.status_code == 200
        assert b"List of blogs this Interpersonal instance can post to" in response.data
    except BaseException as exc:
        print("Authenticated /micropub/ endpoint shoudl display list of blogs")
        print("Response body:")
        print(response.data.decode())
        raise exc


def test_micropub_blog_endpoint_GET_auth(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):

    state = "test state whatever"
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    with app.app_context():

        indieauthfix.login()
        grant_response = indieauthfix.grant(client_id, redir_uri, state)
        authorization_code = indieauthfix.authorization_code_from_grant_response(
            grant_response, redir_uri
        )

        bearer_response = indieauthfix.bearer(authorization_code, client_id, redir_uri)

        unauth_response = client.get("/micropub/example")
        assert unauth_response.status_code == 401
        assert b'"error":"unauthorized"' in unauth_response.data

        bearer_token = json.loads(bearer_response.data)["access_token"]
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {bearer_token}"
        auth_response = client.get("/micropub/example", headers=authheaders)

        assert auth_response.status_code == 400
        assert b"invalid_request" in auth_response.data
        assert (
            b"Valid authorization, but invalid or missing 'q' parameter"
            in auth_response.data
        )


# def test_micropub_blog_endpoint_GET_config():
#     raise NotImplementedError


# def test_micropub_blog_endpoint_GET_source():
#     raise NotImplementedError


# def test_micropub_blog_endpoint_GET_syndicate_to():
#     raise NotImplementedError


# def test_micropub_blog_endpoint_GET_invalid_q():
#     raise NotImplementedError
