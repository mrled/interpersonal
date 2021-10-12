import os
import sqlite3
import typing

import click
from flask import current_app, g
from flask.cli import with_appcontext


# <https://flask.palletsprojects.com/en/2.0.x/tutorial/database/>
# g is a special object that is unique for each request. It is used to store data that might be accessed by multiple functions during the request. The connection is stored and reused instead of creating a new connection if get_db is called a second time in the same request.


# TODO: authTokenUsed could be a foreign key?
CREATE_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS AppSettings(
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS AuthorizationCode(
  authorizationCode TEXT PRIMARY KEY,
  time TIMESTAMP NOT NULL,
  clientId TEXT NOT NULL,
  redirectUri TEXT NOT NULL,
  state TEXT NOT NULL,
  codeChallenge TEXT NOT NULL,
  codeChallengeMethod TEXT NOT NULL,
  scopes TEXT NOT NULL,
  host TEXT NOT NULL,
  used boolean DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS BearerToken(
  bearerToken TEXT PRIMARY KEY,
  time TIMESTAMP NOT NULL,
  authTokenUsed TEXT NOT NULL,
  clientId TEXT NOT NULL,
  scopes TEXT NOT NULL,
  host TEXT NOT NULL,
  revoked boolean DEFAULT FALSE
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DBPATH"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(CREATE_DB_SCHEMA)
    db.commit()


# TODO: have a struct of AppSettings, don't rely on strings for keys?


def set_app_setting(key: str, value: typing.Any):
    """Set a single application setting

    key: The name of the setting
    Value: The new value for the setting
    """
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO AppSettings(key, value) VALUES (?, ?);",
        (key, value),
    )
    db.commit()


def get_app_setting(key: str) -> typing.Any:
    """Retrieve a value from the application settings table

    key: The name of the setting
    """
    db = get_db()
    result = db.execute(
        "SELECT value FROM AppSettings WHERE key = ?", (key,)
    ).fetchone()
    return result["value"]


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Initialize the database schema"""
    init_db()
    click.echo("Initialized the database.")


@click.command("set-login-password")
@click.argument("password")
@with_appcontext
def set_login_password_command(password):
    """Set the IndieAuth login password to PASSWORD"""
    set_app_setting("login_password", password)


@click.command("set-owner-profile")
@click.argument("uri")
@with_appcontext
def set_owner_profile_command(uri):
    """Set the IndieAuth site owner profile uri to URI"""
    set_app_setting("owner_profile", uri)


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(set_login_password_command)
    app.cli.add_command(set_owner_profile_command)


INSERT_AUTHORIZATION_CODE_SQL = """
INSERT INTO AuthorizationCode(
    authorizationCode,
    time,
    clientId,
    redirectUri,
    state,
    codeChallenge,
    codeChallengeMethod,
    scopes,
    host
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


INSERT_BEARER_TOKEN_SQL = """
INSERT INTO BearerToken(
  bearerToken,
  time,
  authTokenUsed,
  clientId,
  scopes,
  host,
) VALUES (?, ?, ?, ?, ?, ?);
"""
