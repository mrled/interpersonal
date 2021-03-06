"""Testing the Flask application factory"""

import os
import tempfile
import textwrap

from interpersonal import create_app


def test_config():
    """Test the application configuration

    Make sure it works in testing mode and in normal mode.
    """
    db_fd, db_path = tempfile.mkstemp()
    conf_fd, conf_path = tempfile.mkstemp()
    media_staging_path = tempfile.mkdtemp()

    appconfig_str = textwrap.dedent(
        f"""\
        ---
        loglevel: DEBUG
        database: {db_path}
        password: whatever
        cookie_secret_key: whocaresman
        uri: http://interpersonal.example.net
        mediastaging: {media_staging_path}
        blogs:
        - name: example
          type: built-in example
          uri: http://whatever.example.net
          sectionmap:
            default: blog
          mediaprefix: /media
        """
    )

    os.write(conf_fd, appconfig_str.encode())

    assert not create_app(configpath=conf_path).testing
    assert create_app({"TESTING": True}, configpath=conf_path).testing

    os.close(db_fd)
    os.unlink(db_path)
    os.close(conf_fd)
    os.unlink(conf_path)
