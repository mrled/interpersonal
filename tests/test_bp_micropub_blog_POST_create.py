import json
from datetime import datetime
from urllib.parse import urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers, MultiDict

from tests.conftest import IndieAuthActions, TestConsts


def test_action_create_post_www_form_urlencoded(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """Content-type of application/x-www-form-urlencoded should parse correctly"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        actest_value = "an testing value,,,"
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        resp = client.post(
            "/micropub/example-blog",
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


def test_action_create_post_www_form_urlencoded_multi_tag(
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
        slug = "form-multi-tag-test"
        posturi = f"{testconstsfix.blog_uri}blog/{slug}"

        # A MultiDict is a Werkzeug data structure that allows duplicate keys.
        # Useful for the tag[] construction, which is meant to convey a list.
        data = MultiDict(
            [
                ["auth_token", z2btd.btoken],
                ["action", "create"],
                ["tag[]", "tagone"],
                ["tag[]", "tagtwo"],
                ["content", "Test content whatever"],
                ["slug", slug],
            ]
        )

        resp = client.post(
            "/micropub/example-blog",
            data=data,
            headers=headers,
        )

        try:
            assert resp.status_code == 201
            assert resp.headers["Location"] == posturi
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise

        # Test that it is gettable
        endpoint = "/micropub/example-blog?" + urlencode(
            {
                "q": "source",
                "url": posturi,
            }
        )
        getresp = client.get(
            endpoint,
            headers=headers,
        )

        try:
            assert getresp.status_code == 200
            json_data = json.loads(getresp.data)
            props = json_data["properties"]
            tags = props["tag"]
            assert "tagone" in tags
            assert "tagtwo" in tags
            app.logger.debug(json.dumps(json_data, indent=2))
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise


def test_action_create_post_json(
    app: Flask, indieauthfix: IndieAuthActions, client: FlaskClient
):
    """JSON posts should parse correctly"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        actest_value = "an testing value,,,"
        resp = client.post(
            "/micropub/example-blog",
            json={
                "auth_token": z2btd.btoken,
                "action": "create",
                "type": ["h-entry"],
                "interpersonal_action_test": actest_value,
                "properties": {
                    "name": ["Test post from json"],
                    "content": [
                        "I'm not sure why json content is in a list like this? can there be more than one item in this list?"
                    ],
                },
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 200
            respjson = json.loads(resp.data)
            assert respjson["action"] == "create"
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_create_post_json_micropub_rocks(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Test json the way micropub.rocks does"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        posturi = f"{testconstsfix.blog_uri}blog/mpr-test-post-one-nice"
        resp = client.post(
            "/micropub/example-blog",
            json={
                "type": ["h-entry"],
                "properties": {
                    "content": ["mpr test post one, nice"],
                },
            },
            headers=headers,
        )

        try:
            assert resp.status_code == 201
            assert resp.headers["Location"] == posturi
        except BaseException:
            print(f"Failing test. Response body: {resp.data}")
            raise


def test_action_create_with_slug(
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
        slug = "test-poast-1"
        post_uri = f"{testconstsfix.blog_uri}blog/{slug}"
        post_content = "Here I am just simply poasting a test poast"
        postresp = client.post(
            "/micropub/example-blog",
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
            assert postresp.status_code == 201
            assert postresp.headers["Location"] == post_uri
        except BaseException:
            print(f"Failing test. Response body: {postresp.data}")
            raise

        # Test that it is gettable
        endpoint = "/micropub/example-blog?" + urlencode(
            {
                "q": "source",
                "url": post_uri,
            }
        )
        getresp = client.get(
            endpoint,
            headers=headers,
        )

        try:
            assert getresp.status_code == 200
            json_data = json.loads(getresp.data)
            props = json_data["properties"]
            pubdate = datetime.strptime(props["published"][0], "%Y-%m-%dT%H:%M:%S")
            now = datetime.utcnow()
            assert pubdate.strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d")
            retrvd_content = props["content"][0]["markdown"].strip()
            assert retrvd_content == post_content
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise


def test_action_create_without_slug(
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
        post_uri = f"{testconstsfix.blog_uri}blog/test-poast-2"
        post_content = "Here I am just simply poasting a second test poast, and relying on automatic slug generation from the title"
        postresp = client.post(
            "/micropub/example-blog",
            data={
                "auth_token": z2btd.btoken,
                "action": "create",
                "h": "entry",
                "content": post_content,
                "name": "tEsT pOaSt -- 2",
                # "tags": "testing",
                # "tags": "poasting",
            },
            headers=headers,
        )

        try:
            assert postresp.status_code == 201
            assert postresp.headers["Location"] == post_uri
        except BaseException:
            print(f"Failing test. Response body: {postresp.data}")
            raise

        # Test that it is gettable
        endpoint = "/micropub/example-blog?" + urlencode(
            {
                "q": "source",
                "url": post_uri,
            }
        )
        getresp = client.get(
            endpoint,
            headers=headers,
        )

        try:
            assert getresp.status_code == 200
            json_data = json.loads(getresp.data)
            props = json_data["properties"]
            pubdate = datetime.strptime(props["published"][0], "%Y-%m-%dT%H:%M:%S")
            now = datetime.utcnow()
            assert pubdate.strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d")
            retrvd_content = props["content"][0]["markdown"].strip()
            assert retrvd_content == post_content
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise


def test_action_create_dupe_should_error(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """If a client requests that we create a post with the same slug as an existing one, should error"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        slug = "test_action_create_dupe_should_error"
        post_uri = f"{testconstsfix.blog_uri}blog/{slug}"
        post_content = "Here I am just simply poasting a test poast for test_action_create_dupe_should_error"
        postresp = client.post(
            "/micropub/example-blog",
            data={
                "auth_token": z2btd.btoken,
                "action": "create",
                "h": "entry",
                "content": post_content,
                "slug": slug,
            },
            headers=headers,
        )

        try:
            assert postresp.status_code == 201
            assert postresp.headers["Location"] == post_uri
        except BaseException:
            print(f"Failing test. Response body: {postresp.data}")
            raise

        # Now try to create it again
        post2resp = client.post(
            "/micropub/example-blog",
            data={
                "auth_token": z2btd.btoken,
                "action": "create",
                "h": "entry",
                "content": post_content,
                "slug": slug,
            },
            headers=headers,
        )

        try:
            assert post2resp.status_code == 400
            p2r_json = json.loads(post2resp.data)
            assert (
                p2r_json["error_description"]
                == f"A post with URI <{post_uri}> already exists"
            )
        except BaseException:
            print(f"Failing test. Response body: {post2resp.data}")
            raise
