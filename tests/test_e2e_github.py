"""Tests we run against the interpersonal test blog.

Requires a github repo that you have a personal access token for.

Does not run by default - requires setting several environment variables.

See readme for details.
"""

import json
import os
from datetime import datetime
from urllib.parse import urlencode

import pytest
from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions, TestConsts


pytestmark = pytest.mark.skipif(
    not os.environ.get("INTERPERSONAL_TEST_GITHUB_RUN_E2E_TESTS"),
    reason="Do not run tests against real Github repos by default",
)


def test_e2e_github_microblog_get_post(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"

        endpoint = f"/micropub/{testconstsfix.github_e2e_blog_name}?" + urlencode(
            {
                "q": "source",
                "url": f"{testconstsfix.github_e2e_blog_uri}/blog/post-one",
            }
        )

        response = client.get(
            endpoint,
            headers=headers,
        )

        try:
            assert response.status_code == 200
            props = json.loads(response.data)["properties"]
            assert "published" in props
            assert "name" in props
            assert props["name"][0] == "Post one"
            post_body = props["content"][0]["markdown"].strip()
            assert post_body == "This is a first post, example."
        except BaseException:
            print(f"Failing test. Response body: {response.data}")
            raise


def test_e2e_github_microblog_create_post(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    with app.app_context():
        post_now = datetime.now()
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        slug = f"blog/test-post-{post_now.timestamp()}"
        post_uri = f"{testconstsfix.github_e2e_blog_uri}{slug}"
        post_content = f"This is a test post created at {post_now} (timestamped {post_now.timestamp()})."
        post_name = f"Test post {post_now.timestamp()}"
        resp = client.post(
            f"/micropub/{testconstsfix.github_e2e_blog_name}",
            data={
                "auth_token": z2btd.btoken,
                "action": "create",
                "h": "entry",
                "content": post_content,
                "slug": slug,
                "name": post_name,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            assert resp.headers["Location"] == post_uri
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise

        # Test that it is gettable
        endpoint = f"/micropub/{testconstsfix.github_e2e_blog_name}?" + urlencode(
            {
                "q": "source",
                "url": post_uri,
            }
        )
        resp = client.get(
            endpoint,
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            json_data = json.loads(resp.data)
            props = json_data["properties"]
            pubdate = datetime.strptime(props["published"][0], "%Y-%m-%dT%H:%M:%S")
            assert pubdate.strftime("%Y-%m-%d") == datetime.now().strftime("%Y-%m-%d")
            assert props["name"][0] == post_name
            retrvd_content = props["content"][0]["markdown"].strip()
            assert retrvd_content == post_content
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise