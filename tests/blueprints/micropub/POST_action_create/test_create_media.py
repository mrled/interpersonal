import json
from urllib.parse import quote, urlencode

from flask.app import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers, MultiDict

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


def test_action_create_post_multipart_form_with_two_files(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Test uploading with a multipart form"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        slug = "test_action_create_post_multipart_form"
        posturi = f"{testconstsfix.blog_uri}blog/{slug}"

        data = MultiDict(
            [
                ["action", "create"],
                ["photo", testconstsfix.img_sing.fstor()],
                ["photo", testconstsfix.img_xeno.fstor(fname="")],
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
            photodata = props["photo"]
            assert len(photodata) == 2
            img_sing_uri = (
                f"{posturi}/{testconstsfix.img_sing.sha256}/singularity-room.jpeg"
            )
            img_xeno_uri = f"{posturi}/{testconstsfix.img_xeno.sha256}/item.jpeg"
            assert photodata[0] == img_sing_uri
            assert photodata[1] == img_xeno_uri
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise


def test_action_create_post_json_with_media(
    app: Flask,
    indieauthfix: IndieAuthActions,
    client: FlaskClient,
    testconstsfix: TestConsts,
):
    """Test uploading media to the media endpoint and referencing it in a JSON post"""
    with app.app_context():
        z2btd = indieauthfix.zero_to_bearer_with_test_data()
        headers = Headers()
        headers["Authorization"] = f"Bearer {z2btd.btoken}"
        postslug = "test_action_create_post_json_with_media"
        posturi = f"{testconstsfix.blog_uri}blog/{postslug}"
        img_subpath = f"{testconstsfix.img_mosaic.sha256}/github-ncsa-mosaic.png"
        imguri_staging = f"{testconstsfix.interpersonal_uri}micropub/example-blog/staging/{img_subpath}"
        imguri_final = f"{posturi}/{img_subpath}"

        media_resp = client.post(
            "/micropub/example-blog/media",
            data={"file": testconstsfix.img_mosaic.fstor()},
            headers=headers,
        )

        try:
            assert media_resp.status_code == 201
            assert media_resp.headers["Location"] == imguri_staging
        except BaseException:
            print(f"Failing media_resp request. Response body: {media_resp.data}")
            raise

        post_resp = client.post(
            "/micropub/example-blog",
            json={
                "action": "create",
                "properties": {
                    "photo": [media_resp.headers["Location"]],
                    "content": ["Test content whatever"],
                    "slug": [postslug],
                },
            },
            headers=headers,
        )

        try:
            assert post_resp.status_code == 201
            assert post_resp.headers["Location"] == posturi
        except BaseException:
            print(f"Failing test. Response body: {post_resp.data}")
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
            photodata = props["photo"]
            assert len(photodata) == 1
            assert photodata[0] == imguri_final
        except BaseException:
            print(f"Failing test. Response body: {getresp.data}")
            raise
