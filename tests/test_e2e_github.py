"""Tests we run against the interpersonal test blog.

Requires a github repo that you have a personal access token for.

Does not run by default - requires setting several environment variables.

See readme for details.
"""

import json
import os
import time
from datetime import datetime
from urllib.parse import urlencode

import pytest
from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from interpersonal.sitetypes import github
from tests.conftest import IndieAuthActions, TestConsts


pytestmark = pytest.mark.skipif(
    not os.environ.get("INTERPERSONAL_TEST_GITHUB_RUN_E2E_TESTS"),
    reason="Do not run tests against real Github repos by default",
)


def test_e2e_github_GithubApiAppJwtAuth_app_installations(
    testconstsfix: TestConsts,
):
    """Test that the list of installations contains the test install.

    The Github app must be created and installed for this test to pass.
    When it is installed, it must have access rights to the test repo.
    """
    ghjwt = github.GithubAppJwt(
        testconstsfix.github_e2e_app_private_key, testconstsfix.github_e2e_app_id
    )
    ghappapi = github.GithubApiAppJwtAuth(ghjwt)
    result = ghappapi.app_installations()
    rowner = testconstsfix.github_e2e_repo_owner
    installs = [i for i in result if i["account"]["login"] == rowner]
    assert len(installs) == 1
    install = installs[0]
    assert install["permissions"]["contents"] == "write"


def test_e2e_github_GithubApiAppJwtAuth_install_token(
    testconstsfix: TestConsts,
):
    """Test that we can find our install token.

    The Github app must be created and installed for this test to pass.
    When it is installed, it must have access rights to the test repo.
    """
    ghjwt = github.GithubAppJwt(
        testconstsfix.github_e2e_app_private_key, testconstsfix.github_e2e_app_id
    )
    ghappapi = github.GithubApiAppJwtAuth(ghjwt)
    rowner = testconstsfix.github_e2e_repo_owner
    result = ghappapi.install_token(rowner)
    print(f"Got resulting token: {result}")
    assert "token" in result
    assert "expires_at" in result
    assert result["permissions"]["contents"] == "write"

    print("Sleeping for 2 secs and then trying again to test the cache")
    time.sleep(2)

    result2 = ghappapi.install_token(rowner)
    print(f"Got resulting token: {result2}")
    assert result["token"] == result2["token"]
    assert result["expires_at"] == result2["expires_at"]


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
        slug = f"test-post-{post_now.timestamp()}"
        post_uri = f"{testconstsfix.github_e2e_blog_uri}blog/{slug}"
        post_content = f"This is a test post created at {post_now} (timestamped {post_now.timestamp()})."
        post_name = f"Test post {post_now.timestamp()}"
        resp = client.post(
            f"/micropub/{testconstsfix.github_e2e_blog_name}",
            data={
                "action": "create",
                "h": "entry",
                "content": post_content,
                "slug": slug,
                "name": post_name,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 201
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
            now = datetime.utcnow()
            assert pubdate.strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d")
            assert props["name"][0] == post_name
            retrvd_content = props["content"][0]["markdown"].strip()
            assert retrvd_content == post_content
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


@pytest.mark.skip
def test_e2e_github_media_endpoint_double_upload_and_delete(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Test that a double-upload works as expected and then delete the result

    Disabled for now because this test is only useful in remote media dir mode,
    but the only testing we do is in local staging mode.

    TODO: Add e2e test blog for remote media dir mode
    TODO: Re-enable this test when there's a test blog in remote media dir mode
    TODO: Add _delete_media() to the base class and have it work for staging mode
    TODO: Test the base class's _delete_media() in another file (not an e2e test, really)
    """
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        imguri = f"https://interpersonal.example.com/micropub/interpersonal-test-blog/media/{testconstsfix.img_mosaic.sha256}/github-ncsa-mosaic.png"

        # Test that the first upload works
        resp1 = client.post(
            f"/micropub/{testconstsfix.github_e2e_blog_name}/media",
            data={"file": testconstsfix.img_mosaic.fstor()},
            headers=headers,
        )
        try:
            assert resp1.status_code == 201
            assert resp1.headers["Location"] == imguri
        except BaseException:
            print(f"Failing test. Response body: {resp1.data}")
            raise

        # Test that the same call works again, but returns 200 not 201 as the file does not need to be re-uploaded
        resp2 = client.post(
            f"/micropub/{testconstsfix.github_e2e_blog_name}/media",
            data={"file": testconstsfix.img_mosaic.fstor()},
            headers=headers,
        )
        try:
            assert resp2.status_code == 200
            assert resp2.headers["Location"] == imguri
        except BaseException:
            print(f"Failing test. Response body: {resp2.data}")
            raise

        # Delete the media item so that our test is idempotent (ish)
        blog: github.HugoGithubRepo = app.config["APPCONFIG"].blog(
            testconstsfix.github_e2e_blog_name
        )
        blog._delete_media([imguri])


def test_e2e_github_upload_media_endpoint_and_reference_in_json_post(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        imguri = f"https://interpersonal.example.com/micropub/interpersonal-test-blog/media/{testconstsfix.img_mosaic.sha256}/github-ncsa-mosaic.png"

        # Upload a file
        upload_resp = client.post(
            f"/micropub/{testconstsfix.github_e2e_blog_name}/media",
            data={"file": testconstsfix.img_mosaic.fstor()},
            headers=headers,
        )
        try:
            assert upload_resp.status_code == 201
            uploaded_imguri = upload_resp.headers["Location"]
            assert uploaded_imguri == imguri
        except BaseException:
            print(f"Failing test. Response body: {upload_resp.data}")
            raise

        post_now = datetime.now()
        slug = f"test-post-{post_now.timestamp()}"
        post_uri = f"{testconstsfix.github_e2e_blog_uri}blog/{slug}"
        post_content = f"![a nice test image]({uploaded_imguri}).\n\nThis is a test post created at {post_now} (timestamped {post_now.timestamp()})."
        post_name = f"Test post {post_now.timestamp()}"
        published_imguri = f"{testconstsfix.github_e2e_blog_uri}blog/{slug}/{testconstsfix.img_mosaic.sha256}/github-ncsa-mosaic.png"

        post_resp = client.post(
            f"/micropub/{testconstsfix.github_e2e_blog_name}",
            json={
                "type": ["h-entry"],
                "properties": {
                    "name": [post_name],
                    "slug": [slug],
                    "content": [post_content],
                    "photo": [uploaded_imguri],
                },
            },
            headers=headers,
        )
        try:
            assert post_resp.status_code == 201
            assert post_resp.headers["Location"] == post_uri
        except BaseException:
            print(f"Failing test. Response body: {post_resp.data}")
            raise

        # Test that it is gettable
        endpoint = f"/micropub/{testconstsfix.github_e2e_blog_name}?" + urlencode(
            {
                "q": "source",
                "url": post_uri,
            }
        )
        post_resp = client.get(
            endpoint,
            headers=headers,
        )

        try:
            assert post_resp.status_code == 200
            json_data = json.loads(post_resp.data)
            content = json_data["properties"]["content"][0]["markdown"]
            print(content)
            assert uploaded_imguri not in content
            assert published_imguri in content
        except BaseException:
            print(f"Failing test. Response body: {post_resp.data}")
            raise