import json
from datetime import datetime
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from tests.conftest import IndieAuthActions, TestConsts


"""
    if action == "create":
        frontmatter = {}
        content = ""
        slug = ""
        content_type = ""
        # TODO: add test for urlencoded body where k ends with [] to indicate an array
        # e.g. ?tag[]=hacking&tag[]=golang should end up with both 'hacking' and 'golang' tags
        for k, v in request_body.items():
            if k == "h":
                content_type = v
            elif k == "content":
                content = v
            elif k == "slug":
                slug = v
            else:
                frontmatter[k] = v
            if not slug:
                raise MicropubInvalidRequestError("Missing 'slug'")
            if not content:
                raise MicropubInvalidRequestError("Missing 'content'")
            if not content_type:
                raise MicropubInvalidRequestError("Missing 'h'")
            if "date" not in frontmatter:
                frontmatter["date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
            blog.add_post(slug, frontmatter, content)

        return json_error(500, "invalid_request", f"Action not yet handled")
    else:
        return json_error(500, f"Unhandled action '{action}'")
"""


def test_action_create_post(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example",
            data={
                "auth_token": z2btd.btoken,
                "action": "create",
                "interpersonal_action_test": actest_value,
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            respjson = json.loads(resp.data)
            assert respjson["interpersonal_test_result"] == actest_value
            assert respjson["action"] == "create"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_create(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        slug = "blog/test-poast-1"
        post_uri = f"{testconstsfix.blog_uri}/{slug}"
        post_content = "Here I am just simply poasting a test poast"
        resp = client.post(
            "/micropub/example",
            data={
                "auth_token": z2btd.btoken,
                "action": "create",
                "h": "entry",
                "content": post_content,
                "slug": slug,
                # "tags": "testing",
                # "tags": "poasting",
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
        endpoint = "/micropub/example?" + urlencode(
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
            retrvd_content = props["content"][0]["markdown"].strip()
            assert retrvd_content == post_content
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise
