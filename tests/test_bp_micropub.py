"""Tests for the micropub blueprint"""


def test_index_requires_auth(client):
    response = client.get("/micropub/")

    try:
        assert response.status_code == 302
        assert b'<a href="/indieauth/login' in response.data
    except BaseException as exc:
        print("/micropub/ index endpoint should require authentication")
        print("Response body:")
        print(response.data.decode())
        raise exc
