"""Tests for the media endpoint"""

import json
import os.path
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers, MultiDict

from tests.conftest import IndieAuthActions, TestConsts


def test_media_endpoint_no_auth_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If there is no authentication mechanism, fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        resp = client.post(
            "/micropub/example-blog/media",
            data={"file": testconstsfix.img_sing.fstor()},
        )

        try:
            assert resp.status_code == 401
            respjson = json.loads(resp.data)
            assert respjson["error_description"] == "Missing Authorization header"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_media_endpoint_wrong_auth_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If the auth token is invalid, fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer ThisIsNotARealTokenLol"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"file": testconstsfix.img_sing.fstor()},
        )

        try:
            assert resp.status_code == 401
            respjson = json.loads(resp.data)
            assert respjson["error_description"] == "Missing Authorization header"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_media_endpoint_auth_in_headers_succeeds(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If the bearer token is in the headers, succeed"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        imguri = f"{testconstsfix.blog_uri}media/{testconstsfix.img_sing.sha256}/singularity-room.jpeg"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"file": testconstsfix.img_sing.fstor()},
            headers=headers,
        )

        try:
            assert resp.status_code == 201
            assert resp.headers["Location"] == imguri
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_media_endpoint_auth_in_body_succeeds(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If the bearer token is in the form body, succeed"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        imguri = f"{testconstsfix.blog_uri}media/{testconstsfix.img_sing.sha256}/singularity-room.jpeg"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"access_token": z2btd.btoken, "file": testconstsfix.img_sing.fstor()},
        )

        try:
            assert resp.status_code == 201
            assert resp.headers["Location"] == imguri
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_media_endpoint_auth_in_both_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If the bearer token is in the form body and also in the headers, fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        imguri = f"{testconstsfix.blog_uri}media/{testconstsfix.img_sing.sha256}/singularity-room.jpeg"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"access_token": z2btd.btoken, "file": testconstsfix.img_sing.fstor()},
            headers=headers,
        )

        try:
            assert resp.status_code == 401
            respjson = json.loads(resp.data)
            assert (
                respjson["error_description"]
                == "Authentication was provided both in HTTP headers and request body"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_media_endpoint_missing_media_scope_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If the bearer token isn't authorized for the media scope, fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data(scopes=["create"])
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        imguri = f"{testconstsfix.blog_uri}media/{testconstsfix.img_sing.sha256}/singularity-room.jpeg"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"file": testconstsfix.img_sing.fstor()},
            headers=headers,
        )

        try:
            assert resp.status_code == 403
            respjson = json.loads(resp.data)
            assert (
                respjson["error_description"]
                == "Access token not valid for action 'media'"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_media_endpoint_www_form_urlencoded_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
):
    """Forms without any files should fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"meaningless_form_field": "meaningless value"},
            headers=headers,
        )
        try:
            assert resp.status_code == 400
            respjson = json.loads(resp.data)
            assert "Invalid Content-type" in respjson["error_description"]
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_create_post_multipart_form_two_files_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Two files should fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog/media",
            data=MultiDict(
                [
                    ["file", testconstsfix.img_sing.fstor()],
                    ["file", testconstsfix.img_xeno.fstor(fname="")],
                ]
            ),
            headers=headers,
        )

        try:
            assert resp.status_code == 400
            respjson = json.loads(resp.data)
            assert (
                respjson["error_description"]
                == "Exactly one file can be submitted at a time, but this request has 2 files"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_create_post_multipart_form_zero_files_fails(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Zero files should fail"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"file_but_with_wrong_name": testconstsfix.img_sing.fstor()},
            headers=headers,
        )

        try:
            assert resp.status_code == 400
            respjson = json.loads(resp.data)
            assert (
                respjson["error_description"]
                == "Exactly one file can be submitted at a time, but this request has 0 files"
            )
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_create_post_multipart_form_single_file_succeeds(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """A single file should succeed"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        imguri = f"{testconstsfix.blog_uri}media/{testconstsfix.img_sing.sha256}/singularity-room.jpeg"
        resp = client.post(
            "/micropub/example-blog/media",
            data={"file": testconstsfix.img_sing.fstor()},
            headers=headers,
        )

        try:
            assert resp.status_code == 201
            assert resp.headers["Location"] == imguri
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise
