import os

from flask import Flask

from interpersonal import database
from interpersonal.blueprints import indieauth, root


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    # Note that the keys here must be in all caps
    app.config.from_mapping(
        DBPATH=os.environ["INTERPERSONAL_DATABASE"],
        SECRET_KEY=os.environ["INTERPERSONAL_COOKIE_SECRET_KEY"],
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    database.init_app(app)

    app.register_blueprint(root.bp)
    app.register_blueprint(indieauth.bp)

    return app
