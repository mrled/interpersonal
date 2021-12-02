"""Tests for miscellaneous actions.

May get refactored into separate files when these acutally get implemented.
"""

import json

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions


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