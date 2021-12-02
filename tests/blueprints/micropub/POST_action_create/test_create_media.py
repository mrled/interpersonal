import json
import os.path
from urllib.parse import quote, urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import FileStorage, Headers

from tests.conftest import IndieAuthActions, TestConsts


def test_action_create_with_photo_from_uri(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Test a photo with photo=

    In this case, Micropub expects that the photo shows up in the post,
    even if it isn't referenced in the post content.

    Also, the photo is given via URI.
    Server can either hotlink or download and embed, per micropub.rocks anyway.

    I will store the 'photo' attribute in the post's frontmatter, but do nothing special about adding it to post HTML.
    I figure that task is best left up to the static site generator.
    """
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        slug = "test_action_create_with_photo"
        post_uri = f"{testconstsfix.blog_uri}blog/{slug}"
        post_content = "Here I am just simply poasting a test poast for test_action_create_with_photo"
        photo_uri = "http://example.com/photo.jpg"
        postresp = client.post(
            "/micropub/example-blog",
            data={
                "action": "create",
                "h": "entry",
                "content": post_content,
                "slug": slug,
                "photo": quote(photo_uri),
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
            retrvd_content = props["content"][0]["markdown"].strip()
            assert retrvd_content == post_content
            retrvd_photo_uri = props["photo"][0]
            assert retrvd_photo_uri == photo_uri
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise


def test_action_create_post_multipart_form(
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
        slug = "test_action_create_post_multipart_form"
        posturi = f"{testconstsfix.blog_uri}blog/{slug}"

        img1 = FileStorage(
            stream=open(testconstsfix.img_jpg_singularity, "rb"),
            filename=os.path.basename(testconstsfix.img_jpg_singularity),
            content_type="image/jpeg",
        )
        img2_no_name = FileStorage(
            stream=open(testconstsfix.img_jpg_xeno, "rb"),
            content_type="image/jpeg",
        )

        resp = client.post(
            "/micropub/example-blog",
            data={
                "action": "create",
                "content": "Test content whatever",
                "slug": slug,
                "testpic1": img1,
                "testpic2": img2_no_name,
            },
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
            app.logger.debug(json.dumps(json_data, indent=2))
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise
