import os
import tempfile

import pytest
from interpersonal import create_app
from interpersonal import database


TEST_SQL_DATA = """
"""


class TestConsts:
    login_password = "test-login-password-123X"
    cookie_secret_key = "test-cookie-secret-key-ASDF-1234"
    owner_profile = "https://interpersonal.example.org/"
    sql_data = TEST_SQL_DATA


@pytest.fixture
def testconstsfix():
    return TestConsts


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()

    app = create_app(
        {
            "TESTING": True,
            "DBPATH": db_path,
            "SECRET_KEY": TestConsts.cookie_secret_key,
        }
    )

    with app.app_context():
        database.init_db()
        database.set_app_setting("login_password", TestConsts.login_password)
        database.set_app_setting("owner_profile", TestConsts.owner_profile)
        database.get_db().executescript(TestConsts.sql_data)

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class IndieAuthActions(object):
    def __init__(self, client):
        self._client = client

    def login(self, password=TestConsts.login_password):
        return self._client.post("/indieauth/login", data={"password": password})

    def logout(self):
        return self._client.get("/indieauth/logout")

    def grant(self, client_id, redirect_uri):
        return self._client.post(
            "/indieauth/grant",
            data={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": "unrandom state for just this test",
            },
        )


@pytest.fixture
def indieauthfix(client):
    return IndieAuthActions(client)
