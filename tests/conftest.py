import json
import os
import tempfile
import typing

import pytest
from interpersonal import create_app
from interpersonal import database


TEST_SQL_DATA = """
"""


TEST_APPCONFIG_YAML_TEMPLATE = """
---
loglevel: DEBUG
database: {db_path}
password: {password}
owner_profile: {owner_profile}
cookie_secret_key: {cookie_secret_key}
blogs:
  - name: example
    type: built-in example
    uri: {baseuri}
"""


class TestConsts:
    login_password = "test-login-password-123X"
    cookie_secret_key = "test-cookie-secret-key-ASDF-1234"
    owner_profile = "https://interpersonal.example.org/"
    sql_data = TEST_SQL_DATA
    blog_uri = "http://interpersonal.example.org"


@pytest.fixture
def testconstsfix():
    return TestConsts


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    conf_fd, conf_path = tempfile.mkstemp()

    appconfig_str = TEST_APPCONFIG_YAML_TEMPLATE.format(
        db_path=db_path,
        password=TestConsts.login_password,
        owner_profile=TestConsts.owner_profile,
        cookie_secret_key=TestConsts.cookie_secret_key,
        baseuri=TestConsts.blog_uri,
    )
    os.write(conf_fd, appconfig_str.encode())

    app = create_app(
        test_config={
            "TESTING": True,
        },
        configpath=conf_path,
    )

    with app.app_context():
        database.init_db()
        database.get_db().executescript(TestConsts.sql_data)

    yield app

    os.close(db_fd)
    os.unlink(db_path)
    os.close(conf_fd)
    os.unlink(conf_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class ZeroToBearerTestData(typing.NamedTuple):
    client_id: str
    redirect_uri: str
    state: str
    scopes: typing.List[str]
    btoken: str


class IndieAuthActions(object):
    def __init__(self, client):
        self._client = client

    def login(self, password=TestConsts.login_password):
        return self._client.post("/indieauth/login", data={"password": password})

    def logout(self):
        return self._client.get("/indieauth/logout")

    def grant(
        self, client_id: str, redirect_uri: str, state: str, scopes: typing.List[str]
    ):
        data = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": None,
            "code_challenge_method": None,
            "me": TestConsts.owner_profile,
        }
        for scope in scopes:
            data[f"scope:{scope}"] = "on"
        return self._client.post("/indieauth/grant", data=data)

    def authorization_code_from_grant_response(self, grant_response, redirect_uri):
        """Parse the authorization code out from the the response to /indieauth/grant"""
        return (
            grant_response.data.decode()
            .split(f"{redirect_uri}?code=")[1]
            .split("&amp;")[0]
        )

    def bearer(self, authorization_code, client_id, redirect_url):
        return self._client.post(
            "/indieauth/bearer",
            # the data= argument passes application/x-www-form-urlencoded
            # which is what /indieauth/bearer should accept
            data={
                "code": authorization_code,
                "me": TestConsts.owner_profile,
                "client_id": client_id,
                "redirect_uri": redirect_url,
            },
        )

    def zero_to_bearer(
        self, client_id: str, redirect_uri: str, state: str, scopes: typing.List[str]
    ):
        """Start from scratch and get a bearer token.

        Log in, grant access, parse the authorization code, exchange the authorization code for a bearer token, and return the bearer response
        """
        self.login()
        granted = self.grant(client_id, redirect_uri, state, scopes)
        authcode = self.authorization_code_from_grant_response(granted, redirect_uri)
        bearer_resp = self.bearer(authcode, client_id, redirect_uri)
        bearer_json = json.loads(bearer_resp.data)
        btoken = bearer_json["access_token"]

        # Don't confuse cookie authentication (self.login())
        # with token authentication
        self.logout()

        return btoken

    def zero_to_bearer_with_test_data(
        self,
        client_id: str = "https://client.example.net/",
        redirect_uri: str = "https://client.example.net/",
        state: str = "test state whatever",
        scopes: typing.List[str] = ["create"],
    ):
        """Start from scratch and get a bearer token.

        Use some predefined test data and return it in a ZeroToBearerTestData object.
        """
        btoken = self.zero_to_bearer(client_id, redirect_uri, state, scopes)
        return ZeroToBearerTestData(client_id, redirect_uri, state, scopes, btoken)


@pytest.fixture
def indieauthfix(client):
    return IndieAuthActions(client)
