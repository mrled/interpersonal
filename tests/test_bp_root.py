"""Tests for the root blueprint"""


def test_hello(client):
    response = client.get("/hello")
    assert (
        response.data
        == b"Hello from Interpersonal, the connection between my little site and the indie web"
    )
