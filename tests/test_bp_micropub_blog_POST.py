"""Tests for /micropub/<blog> GET requests"""

import io
import json
import os
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import FileStorage, Headers

from tests.conftest import IndieAuthActions, TestConsts


def test_micropub_blog_endpoint_POST_unauth_fails(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    with app.app_context():
        # Log in and get a bearer token, but don't use it
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        unauth_response = client.post(
            "/micropub/example-blog",
            data={"content": "Post body for test post that should fail anyway"},
        )
        try:
            assert unauth_response.status_code == 401
            unauth_response_json = json.loads(unauth_response.data)
            assert unauth_response_json["error"] == "unauthorized"
            assert (
                unauth_response_json["error_description"]
                == "Missing Authorization header"
            )
        except BaseException:
            print(f"Failing test. Response body: {unauth_response.data}")
            raise


def test_auth_in_header(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Test for authentication in the header

    > If the request has an Authorization: Bearer header, set access_token to the value of the string after Bearer , stripping whitespace.
    """
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {z2btd.btoken}"
        authheaders["X-Interpersonal-Auth-Test"] = "yes"
        auth_response = client.post(
            "/micropub/example-blog",
            data={
                "content": "This is content to a test post that doesn't matter at all"
            },
            headers=authheaders,
        )

        try:
            assert auth_response.status_code == 200
            auth_response_json = json.loads(auth_response.data)
            assert (
                auth_response_json["interpersonal_test_result"]
                == "authentication_success"
            )
        except BaseException:
            print(f"Failing test. Response body: {auth_response.data}")
            raise


def test_auth_in_form(app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient):
    """Test for authentication in the form-encoded request body.

    > if the method is POST and the parsed content of the form-encoded request body contains an access_token key, set access_token to the value associated with that key
    """
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["X-Interpersonal-Auth-Test"] = "yes"

        # When passing a dict to data=, the Content-type is automatically set
        # to x-www-form-urlencoded
        # headers["Content-type"] = "application/x-www-form-urlencoded"
        auth_response = client.post(
            "/micropub/example-blog",
            data={"access_token": z2btd.btoken},
            headers=headers,
        )

        assert auth_response.status_code == 200
        auth_response_json = json.loads(auth_response.data)
        assert (
            auth_response_json["interpersonal_test_result"] == "authentication_success"
        )


# def test_json_body_authentication(
#     app: Flask,
#     indieauthfix: IndieAuthActions,
#     client: FlaskClient,
#     testconstsfix: TestConsts,
# ):
#     """POST request with JSON body should auth with access token in body as JSON property
#
#     TODO: Implement me
#     """
#     raise NotImplementedError


def test_missing_content_type_fails(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """If Content-type is not set, the POST should fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        authheaders = Headers()
        authheaders["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post("/micropub/example-blog", headers=authheaders)

        assert resp.status_code == 400
        respjson = json.loads(resp.data)
        assert respjson["error"] == "invalid_request"
        assert respjson["error_description"] == "No 'Content-type' header"


def test_content_type_app_json(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Content-type of application/json should parse correctly"""
    contype_test_value = "yes, please, nice ok"

    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        # Passing a dict to data= will set Content-type to application/x-www-form-urlencoded
        resp = client.post(
            "/micropub/example-blog",
            json={
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
            "/micropub/example-blog",
            data={
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
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Content-type of multipart/form-data should parse correctly"""
    contype_test_value = "yes, please, nice ok"

    test_file_data_1 = (io.BytesIO("test file contents 1".encode("utf8")), "test_1.txt")
    test_file_data_2 = (
        io.BytesIO("test file contents TWO".encode("utf8")),
        "test_2.txt",
    )
    img1_jpg = FileStorage(
        stream=open(testconstsfix.img_jpg_singularity, "rb"),
        filename=os.path.basename(testconstsfix.img_jpg_singularity),
        content_type="image/jpeg",
    )
    img2_jpg_no_name = FileStorage(
        stream=open(testconstsfix.img_jpg_xeno, "rb"),
        content_type="image/jpeg",
    )
    img3_png = FileStorage(
        stream=open(testconstsfix.img_png_mosaic, "rb"), content_type="image/png"
    )

    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        # Passing a dict to data= will set Content-type to application/x-www-form-urlencoded
        # If the dict has a "file" key, it will be sent as multipart/form-data
        resp = client.post(
            "/micropub/example-blog",
            data={
                "interpersonal_content-type_test": contype_test_value,
                "file": [test_file_data_1, test_file_data_2],
                "photo": [img1_jpg, img2_jpg_no_name, img3_png],
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            # Response like: {"interpersonal_test_result": contype_test, "content_type": content_type}
            respjson = json.loads(resp.data)
            assert respjson["interpersonal_test_result"] == contype_test_value
            assert respjson["content_type"].startswith("multipart/form-data")
            # The files should be ignored, and only the photos should be counted
            assert respjson["uploaded_file_count"] == 3
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


## TODO: Test that video and audio uploads work too


def test_action_delete(app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient):
    """Delete action should fail for now"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["delete"])
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "action": "delete",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 400
            respjson = json.loads(resp.data)
            assert respjson["error"] == "invalid_request"
            assert respjson["error_description"] == "'delete' action not supported"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_undelete(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Undelete action should fail for now"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["undelete"])
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "action": "undelete",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 400
            respjson = json.loads(resp.data)
            assert respjson["error"] == "invalid_request"
            assert respjson["error_description"] == "'undelete' action not supported"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_modify(app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient):
    """Update action should fail for now"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["update"])
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "action": "update",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 400
            respjson = json.loads(resp.data)
            assert respjson["error"] == "invalid_request"
            assert respjson["error_description"] == "'update' action not supported"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_invalid(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Invalid actions will show as scoped incorrectly, because the scoping system only accepts known hardcoded scopes"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["invalid"])
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "action": "invalid",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 403
            respjson = json.loads(resp.data)
            assert respjson["error"] == "insufficient_scope"
            assert (
                respjson["error_description"]
                == "Access token not valid for action 'invalid'"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_scope_invalid(app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient):
    """Requests usint a key not scoped for them should fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["create"])
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "action": "delete",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 403
            respjson = json.loads(resp.data)
            assert respjson["error"] == "insufficient_scope"
            assert (
                respjson["error_description"]
                == "Access token not valid for action 'delete'"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_auth_headers_and_form_body_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If the access token is provided in both headers and form body, the request should fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["create"])
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "access_token": z2btd.btoken,
                "action": "delete",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 401
            respjson = json.loads(resp.data)
            assert respjson["error"] == "unauthorized"
            assert (
                respjson["error_description"]
                == "Authentication was provided both in HTTP headers and request body"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_form_body_auth_doesnt_work_with_wrong_name(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """At first I erroneously used 'auth_token', but micropub requires 'access_token'.

    Make sure that the wrong name does not authenticate.
    """
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["create"])
        actest_value = "an testing value,,,"
        resp = client.post(
            "/micropub/example-blog",
            data={
                "auth_token": z2btd.btoken,
                "action": "delete",
                "interpersonal_action_test": actest_value,
            },
        )

        try:
            assert resp.status_code == 401
            respjson = json.loads(resp.data)
            assert respjson["error"] == "unauthorized"
            assert respjson["error_description"] == "Missing Authorization header"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise
