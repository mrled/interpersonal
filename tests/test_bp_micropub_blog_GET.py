"""Tests for /micropub/<blog> GET requests"""

import json
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions, TestConsts


def test_micropub_blog_endpoint_GET_auth(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):

    state = "test state whatever"
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"

    with app.app_context():
        btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

        unauth_response = client.get("/micropub/example")
        assert unauth_response.status_code == 401
        unauth_data_json = json.loads(unauth_response.data)
        assert unauth_data_json["error"] == "unauthorized"
        assert unauth_data_json["error_description"] == "Missing Authorization header"
        assert b'"error":"unauthorized"' in unauth_response.data

        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {btoken}"
        auth_response = client.get("/micropub/example", headers=authheaders)

        assert auth_response.status_code == 400
        assert b"invalid_request" in auth_response.data
        assert (
            b"Valid authorization, but invalid or missing 'q' parameter"
            in auth_response.data
        )


def test_micropub_blog_endpoint_GET_config(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    state = "test state whatever"
    btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

    with app.app_context():
        headers = Headers()
        headers["Authorization"] = f"Bearer {btoken}"
        response = client.get("/micropub/example?q=config", headers=headers)

        assert response.status_code == 200
        response_json = json.loads(response.data)
        assert "media-endpoint" in response_json
        assert response_json["media-endpoint"] == "/micropub/example/media"


def test_micropub_blog_endpoint_GET_source_valid_url(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    state = "test state whatever"
    btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

    with app.app_context():
        headers = Headers()
        headers["Authorization"] = f"Bearer {btoken}"

        endpoint = "/micropub/example?" + urlencode(
            {
                "q": "source",
                "url": f"{testconstsfix.blog_uri}/blog/post-one",
            }
        )

        response = client.get(
            endpoint,
            headers=headers,
        )
        assert response.status_code == 200
        # Should be something like this:
        # {'date': 'Wed, 27 Jan 2021 00:00:00 GMT', 'tags': ['billbert', 'bobson'], 'title': 'Post one'}
        response_json = json.loads(response.data)
        assert "date" in response_json
        assert "tags" in response_json
        assert "title" in response_json
        assert response_json["title"] == "Post one"


def test_micropub_blog_endpoint_GET_source_invalid_url(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    state = "test state whatever"
    btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

    with app.app_context():
        headers = Headers()
        headers["Authorization"] = f"Bearer {btoken}"

        endpoint = "/micropub/example?" + urlencode(
            {
                "q": "source",
                "url": f"{testconstsfix.blog_uri}/blog/invalid-post-url-ASDF",
            }
        )

        response = client.get(
            endpoint,
            headers=headers,
        )
        assert response.status_code == 404
        # Should be something like this:
        # {'error': 'no such blog post', 'error_description': ''}
        response_json = json.loads(response.data)
        assert "error" in response_json
        assert response_json["error"] == "no such blog post"


def test_micropub_blog_endpoint_GET_source_no_url(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    state = "test state whatever"
    btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

    with app.app_context():
        headers = Headers()
        headers["Authorization"] = f"Bearer {btoken}"

        endpoint = "/micropub/example?" + urlencode(
            {
                "q": "source",
            }
        )

        response = client.get(
            endpoint,
            headers=headers,
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert "error" in response_json
        assert response_json["error"] == "invalid_request"


def test_micropub_blog_endpoint_GET_syndicate_to(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    state = "test state whatever"
    btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

    with app.app_context():
        headers = Headers()
        headers["Authorization"] = f"Bearer {btoken}"

        endpoint = "/micropub/example?" + urlencode(
            {
                "q": "syndicate-to",
            }
        )
        response = client.get(
            endpoint,
            headers=headers,
        )

        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert "error" in response_json
        assert response_json["error"] == "invalid_request"


def test_micropub_blog_endpoint_GET_invalid_q(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
):
    client_id = "https://client.example.net/"
    redir_uri = "https://client.example.net/redir/to/here"
    state = "test state whatever"
    btoken = indieauthfix.zero_to_bearer(client_id, redir_uri, state, ["create"])

    with app.app_context():
        headers = Headers()
        headers["Authorization"] = f"Bearer {btoken}"

        endpoint = "/micropub/example?" + urlencode(
            {
                "q": "something-invalid-QWER",
            }
        )
        response = client.get(
            endpoint,
            headers=headers,
        )

        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert "error" in response_json
        assert response_json["error"] == "invalid_request"