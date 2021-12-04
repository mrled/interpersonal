import logging
import os

import yaml
from flask import Flask

from interpersonal import database
from interpersonal.appconfig import AppConfig
from interpersonal.blueprints import indieauth, micropub, root


def add_security_headers(resp):
    """Add headers to routes

    See also:
    - <https://content-security-policy.com>
    - <https://flask.palletsprojects.com/en/2.0.x/security/>
    - <https://scotthelme.co.uk/tough-cookies/>

    Some of these may be redundant with CSP? Hard to keep track.
    """
    headers = {
        "Content-Security-Policy": "default-src 'none'; script-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",  # Redundant with frame-ancestors ?
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",  # Redundant?
        "Sec-Fetch-Site": "same-site",
        "Permissions-Policy": "sync-xhr=(), accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Interpersonal-Message": "Generated by Interpersonal, <https://github.com/mrled/interpersonal>",
        "X-Content-Type-Options": "nosniff",
    }
    resp.headers.update(**headers)
    return resp


def create_app(
    test_config=None,
    configpath=os.environ.get("INTERPERSONAL_CONFIG"),
):

    try:
        appconfig = AppConfig.fromyaml(configpath)
    except BaseException as exc:
        print(f"ERROR! loading interpersonal configuration file: {exc}")
        raise

    app = Flask(__name__, instance_relative_config=True)

    app.logger.setLevel(logging.getLevelName(appconfig.loglevel))

    # Note that the keys here must be in all caps
    app.config.from_mapping(
        # The path to the sqlite database
        DBPATH=appconfig.database,
        # A valid AppConfig object
        APPCONFIG=appconfig,
        # A secret, random value used to encrypt the session cookie
        SECRET_KEY=appconfig.cookie_secret_key,
        # Require HTTPS before setting the session cookie
        SESSION_COOKIE_SECURE=True,
        # Prevents sending cookies with CSRF-prone requests (eg forms) from external sites
        # Still allows regular links (regular GET requests) from external sites
        # to let the browser see the cookie if I'm already logged in.
        SESSION_COOKIE_SAMESITE="Lax",
        # Use the `__Host-` prefix for the session cookie name, which increases security somewhat.
        SESSION_COOKIE_NAME="__Host-session",
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    database.init_app(app)

    app.register_blueprint(root.bp)
    app.register_blueprint(indieauth.bp)
    app.register_blueprint(micropub.bp)

    # Actually apply the add_security_headers() function to all responses
    @app.after_request
    def addsechead(resp):
        return add_security_headers(resp)

    return app
