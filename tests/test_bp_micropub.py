"""Tests for the micropub blueprint"""


from flask.testing import FlaskClient

from tests.conftest import IndieAuthActions


def test_index_requires_auth(client: FlaskClient):
    response = client.get("/micropub/")

    try:
        assert response.status_code == 302
        assert b'<a href="/indieauth/login' in response.data
    except BaseException as exc:
        print("/micropub/ index endpoint should require authentication")
        print("Response body:")
        print(response.data.decode())
        raise exc


def test_index_with_auth_shows_blog_list(
    client: FlaskClient, indieauthfix: IndieAuthActions
):
    indieauthfix.login()

    response = client.get("/micropub/")

    try:
        assert response.status_code == 200
        assert b"List of blogs this Interpersonal instance can post to" in response.data
    except BaseException as exc:
        print("Authenticated /micropub/ endpoint shoudl display list of blogs")
        print("Response body:")
        print(response.data.decode())
        raise exc
