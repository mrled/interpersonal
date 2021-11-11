"""Tests for /micropub/<blog> GET requests"""

import json
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions, TestConsts


def test_micropub_blog_endpoint_POST_unauth_fails(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):

    state = "test state whatever"
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    with app.app_context():
        # Log in and get a bearer token, but don't use it
        bearer_token = indieauthfix.zero_to_bearer(client_id, redir_uri, state)
        unauth_response = client.post("/micropub/example")
        assert unauth_response.status_code == 401
        unauth_response_json = json.loads(unauth_response.data)
        assert unauth_response_json["error"] == "unauthorized"
        assert (
            unauth_response_json["error_description"] == "Missing Authorization header"
        )


def test_auth_in_header(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Test for authentication in the header

    > If the request has an Authorization: Bearer header, set auth_token to the value of the string after Bearer , stripping whitespace.
    """

    state = "test state whatever"
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    with app.app_context():
        bearer_token = indieauthfix.zero_to_bearer(client_id, redir_uri, state)
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {bearer_token}"
        authheaders["X-Interpersonal-Auth-Test"] = "yes"
        auth_response = client.post("/micropub/example", headers=authheaders)

        assert auth_response.status_code == 200
        auth_response_json = json.loads(auth_response.data)
        assert (
            auth_response_json["interpersonal_test_result"] == "authentication_success"
        )


def test_auth_in_form(app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient):
    """Test for authentication in the form-encoded request body.

    > if the method is POST and the parsed content of the form-encoded request body contains an auth_token key, set auth_token to the value associated with that key
    """
    state = "test state whatever"
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    with app.app_context():
        bearer_token = indieauthfix.zero_to_bearer(client_id, redir_uri, state)
        headers = Headers()
        headers["X-Interpersonal-Auth-Test"] = "yes"

        # When passing a dict to data=, the Content-type is automatically set
        # to x-www-form-urlencoded
        # headers["Content-type"] = "application/x-www-form-urlencoded"
        auth_response = client.post(
            "/micropub/example", data={"auth_token": bearer_token}, headers=headers
        )

        assert auth_response.status_code == 200
        auth_response_json = json.loads(auth_response.data)
        assert (
            auth_response_json["interpersonal_test_result"] == "authentication_success"
        )


def test_missing_content_type_fails(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """If Content-type is not set, the POST should fail"""
    state = "test state whatever"
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    with app.app_context():
        bearer_token = indieauthfix.zero_to_bearer(client_id, redir_uri, state)
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {bearer_token}"
        resp = client.post("/micropub/example", headers=authheaders)

        assert resp.status_code == 400
        respjson = json.loads(resp.data)
        assert respjson["error"] == "invalid_request"
        assert respjson["error_description"] == "No 'Content-type' header"


def test_content_type_app_json():
    pass


def test_content_type_urlencoded_form():
    pass


def test_content_type_multipart_form():
    pass