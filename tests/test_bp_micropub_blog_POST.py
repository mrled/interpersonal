"""Tests for /micropub/<blog> GET requests"""

import io
import json
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions, TestConsts


def test_micropub_blog_endpoint_POST_unauth_fails(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    with app.app_context():
        # Log in and get a bearer token, but don't use it
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
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
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {z2btd.btoken}"
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
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["X-Interpersonal-Auth-Test"] = "yes"

        # When passing a dict to data=, the Content-type is automatically set
        # to x-www-form-urlencoded
        # headers["Content-type"] = "application/x-www-form-urlencoded"
        auth_response = client.post(
            "/micropub/example", data={"auth_token": z2btd.btoken}, headers=headers
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
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post("/micropub/example", headers=authheaders)

        assert resp.status_code == 400
        respjson = json.loads(resp.data)
        assert respjson["error"] == "invalid_request"
        assert respjson["error_description"] == "No 'Content-type' header"


def test_content_type_app_json(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    contype_test_value = "yes, please, nice ok"

    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        # Passing a dict to data= will set Content-type to application/x-www-form-urlencoded
        resp = client.post(
            "/micropub/example",
            json={
                "auth_token": z2btd.btoken,
                "interpersonal_content-type_test": contype_test_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            # Response like: {"interpersonal_test_result": contype_test, "content_type": content_type}
            respjson = json.loads(resp.data)
            assert respjson["interpersonal_test_result"] == contype_test_value
            assert respjson["content_type"] == "application/json"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_content_type_urlencoded_form(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    contype_test_value = "yes, please, nice ok"

    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        # Passing a dict to data= will set Content-type to application/x-www-form-urlencoded
        resp = client.post(
            "/micropub/example",
            data={
                "auth_token": z2btd.btoken,
                "interpersonal_content-type_test": contype_test_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            # Response like: {"interpersonal_test_result": contype_test, "content_type": content_type}
            respjson = json.loads(resp.data)
            assert respjson["interpersonal_test_result"] == contype_test_value
            assert respjson["content_type"] == "application/x-www-form-urlencoded"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_content_type_multipart_form(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    contype_test_value = "yes, please, nice ok"

    test_file_data_1 = (io.BytesIO("test file contents 1".encode("utf8")), "test_1.txt")
    test_file_data_2 = (
        io.BytesIO("test file contents TWO".encode("utf8")),
        "test_2.txt",
    )

    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        # Passing a dict to data= will set Content-type to application/x-www-form-urlencoded
        # If the dict has a "file" key, it will be sent as multipart/form-data
        resp = client.post(
            "/micropub/example",
            data={
                "auth_token": z2btd.btoken,
                "interpersonal_content-type_test": contype_test_value,
                "file": [test_file_data_1, test_file_data_2],
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            # Response like: {"interpersonal_test_result": contype_test, "content_type": content_type}
            respjson = json.loads(resp.data)
            assert respjson["interpersonal_test_result"] == contype_test_value
            assert respjson["content_type"].startswith("multipart/form-data")
            assert "test_1.txt" in respjson["filenames"]
            assert "test_2.txt" in respjson["filenames"]
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise
