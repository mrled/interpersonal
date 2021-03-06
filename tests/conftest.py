import json
import os
import shutil
import tempfile
import typing

import pytest
from werkzeug.datastructures import FileStorage
from interpersonal import create_app
from interpersonal import database


TEST_APPCONFIG_YAML_TEMPLATE = """
---
loglevel: DEBUG
database: {db_path}
password: {password}
cookie_secret_key: {cookie_secret_key}
uri: {interpersonal_uri}
mediastaging: {mediastaging}
blogs:
  - name: example-blog
    type: built-in example
    uri: {blog_uri}
    sectionmap:
        default: blog
        bookmark: bookmarks
  - name: {github_e2e_blog_name}
    type: github
    uri: {github_e2e_blog_uri}
    github_owner: {github_e2e_repo_owner}
    github_repo: {github_e2e_repo_name}
    github_repo_branch: master
    github_app_id: {github_e2e_app_id}
    github_app_private_key: {github_e2e_app_private_key}
    sectionmap:
        default: blog
        bookmark: bookmarks
"""


def datafile(name):
    """Build a path for files in ./data/"""
    return os.path.join(os.path.dirname(__file__), "data", name)


class TestDataFile:
    """A test data file, inside of tests/data/"""

    def __init__(self, relpath: str, sha256: str, content_type: str):
        """Initializer

        relpath:                The path to the data file, relative to tests/data/.
        content_type:           The actual content type of the file
        """
        self.relpath = relpath
        self.path = datafile(relpath)
        self.sha256 = sha256
        self.content_type = content_type

    def fstor(
        self,
        contype: typing.Union[str, None] = None,
        fname: typing.Union[str, None] = None,
    ):
        """Get a FileStorage object

        content_type:           A MIME type.
        override_filename:      Either a string, or None.
                                If None, use the basename as the filename.
                                If a string, override with the string.
                                (You can set the string to "", meaning no filename.)
        override_type:          Either a string, or None.
                                If None, use the actual content type (from initializer).
                                If a string, override with the string.
        """
        if fname is None:
            filename = os.path.basename(self.path)
        else:
            filename = fname
        if contype is None:
            content_type = self.content_type
        else:
            content_type = contype
        return FileStorage(
            stream=open(self.path, "rb"),
            filename=filename,
            content_type=content_type,
        )


class TestConsts:
    login_password = "test-login-password-123X"
    cookie_secret_key = "test-cookie-secret-key-ASDF-1234"
    interpersonal_uri = "https://interpersonal.example.com/"
    blog_uri = "https://blog.example.org/"

    github_e2e_blog_name = "interpersonal-test-blog"
    github_e2e_blog_uri = os.environ.get("INTERPERSONAL_TEST_GITHUB_BLOG_URI")
    github_e2e_repo_owner = os.environ.get("INTERPERSONAL_TEST_GITHUB_OWNER")
    github_e2e_repo_name = os.environ.get("INTERPERSONAL_TEST_GITHUB_REPO")
    github_e2e_app_id = os.environ.get("INTERPERSONAL_TEST_GITHUB_APP_ID")
    github_e2e_app_private_key = os.environ.get(
        "INTERPERSONAL_TEST_GITHUB_APP_PRIVATE_KEY"
    )

    img_mosaic = TestDataFile(
        "github-ncsa-mosaic.png",
        "a1f725d5d91ef519f989cb81c1169ab3ff0439af7429c449f51ea275c84914b1",
        "image/png",
    )
    img_sing = TestDataFile(
        "singularity-room.jpg",
        "9b242403c78bd2e944eefc8288d5f534928f615e8f5699ef7eb9cc10aac9f2fe",
        "image/jpeg",
    )
    img_xeno = TestDataFile(
        "xenomorph-formal.jpg",
        "dbfb0e4f58b2026a3bd2cc1f052f5af46168e94d8c45d5916d77ce2f37c35c65",
        "image/jpeg",
    )


@pytest.fixture
def testconstsfix():
    return TestConsts


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    conf_fd, conf_path = tempfile.mkstemp()
    media_staging_path = tempfile.mkdtemp()

    appconfig_str = TEST_APPCONFIG_YAML_TEMPLATE.format(
        db_path=db_path,
        password=TestConsts.login_password,
        cookie_secret_key=TestConsts.cookie_secret_key,
        interpersonal_uri=TestConsts.interpersonal_uri,
        blog_uri=TestConsts.blog_uri,
        mediastaging=media_staging_path,
        github_e2e_blog_name=TestConsts.github_e2e_blog_name,
        github_e2e_blog_uri=TestConsts.github_e2e_blog_uri,
        github_e2e_repo_owner=TestConsts.github_e2e_repo_owner,
        github_e2e_repo_name=TestConsts.github_e2e_repo_name,
        github_e2e_app_id=TestConsts.github_e2e_app_id,
        github_e2e_app_private_key=TestConsts.github_e2e_app_private_key,
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

    yield app

    os.close(db_fd)
    os.unlink(db_path)
    os.close(conf_fd)
    os.unlink(conf_path)
    shutil.rmtree(media_staging_path)


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
            "me": TestConsts.blog_uri,
        }
        for scope in scopes:
            data[f"scope:{scope}"] = "on"
        return self._client.post("/indieauth/grant/example-blog", data=data)

    def authorization_code_from_grant_response(self, grant_response, redirect_uri):
        """Parse the authorization code out from the the response to /indieauth/grant"""
        return (
            grant_response.data.decode()
            .split(f"{redirect_uri}?code=")[1]
            .split("&amp;")[0]
        )

    def bearer(self, authorization_code, client_id, redirect_url):
        return self._client.post(
            "/indieauth/bearer/example-blog",
            # the data= argument passes application/x-www-form-urlencoded
            # which is what /indieauth/bearer should accept
            data={
                "code": authorization_code,
                "me": TestConsts.blog_uri,
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
        scopes: typing.List[str] = ["create", "media"],
    ):
        """Start from scratch and get a bearer token.

        Use some predefined test data and return it in a ZeroToBearerTestData object.
        """
        btoken = self.zero_to_bearer(client_id, redirect_uri, state, scopes)
        return ZeroToBearerTestData(client_id, redirect_uri, state, scopes, btoken)


@pytest.fixture
def indieauthfix(client):
    return IndieAuthActions(client)
