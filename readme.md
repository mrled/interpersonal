# Interpersonal

The connection between my little site and the Indie Web.

## Implementation

This code benefitted greatly from <https://unrelenting.technology>'s
[Sellout Engine](https://github.com/unrelentingtech/sellout),
and also from the [Flask tutorial](https://flask.palletsprojects.com/en/2.0.x/tutorial/).

### Documentation

Some notes on design decisions, etc.

- [Tokens and codes and secrets](./docs/secrets.md)
- [WSGI, not ASGI](./docs/wsgi.md)
- [To do](./docs/todo.md)
- [Pytest and pdb](./docs/pytest-pdb.md)
- [fast.ai's GhApi Python module](./docs/ghapi.md)
- [Github app](./docs/github-app.md)

## Development

Set up a venv:

```sh
python3 -m venv interpersonal.venv
. interpersonal.venv/bin/activate
pip install -e .
```

Run in development mode.
Note that you can set the owner profile to a dummy example URL
and still see some pages and make all the tests work.
You can also set it to a live site or a site you're running locally.
See `dev.conf.yml` for configuration.

```sh
. dev.env
flask init-db  # Initialize the database
flask run --debugger  # Run the webserver
```

Run the tests and code coverage:

```sh
# Run just the tests
pytest

# Calculate code coverage
coverage run -m pytest
coverage report
```

### Running the end-to-end tests

To run the e2e tests against the real github repo, you need a repo to run against.
Mine is <https://github.com/mrled/interpersonal-test-blog>.

You also need to create a [Github App](./docs/github-app.md)

Then:

```sh
# You don't actually have to deploy this to netlify or anywhere, but I did
# If you don't deploy it, you can use an example.com URL for the blog
export INTERPERSONAL_TEST_GITHUB_BLOG_URI=https://interpersonal-test-blog.netlify.app/
# The owner of the github repo
export INTERPERSONAL_TEST_GITHUB_OWNER=mrled
# The name of the github repo
export INTERPERSONAL_TEST_GITHUB_REPO=interpersonal-test-blog
# This will be a number that Github assigns your app
export INTERPERSONAL_TEST_GITHUB_APP_ID=153329
# The private key that Github generated
export INTERPERSONAL_TEST_GITHUB_APP_PRIVATE_KEY=./interpersonal-micahrl-com.2021-11-20.private-key.pem

INTERPERSONAL_TEST_GITHUB_RUN_E2E_TESTS=true pytest tests/test_e2e_github.py
```

Note that actually deploying this on Netlify (or anywhere else) is not necessary,
as you can just check the status of your commits on github.com.
The blog URI isn't used for anything either.
That said, in this case I did actually deploy to Netlify, so that is a real URL.
(Is it weird that it's satisfying to see my test posts show up on the deployed site?)

### Cert errors on macOS

For some reason you have to run `sudo /Applications/Python\ $version/Install\ Certificates.command` (e.g. for Python 3.9 `sudo /Applications/Python\ 3.9/Install\ Certificates.command`) to fix certificate errors when running on macOS.

If you're getting errors like `CERTIFICATE_VERIFY_FAILED` when trying to talk to the Github API, this may be your issue.

## Production

First, you need to create a [Github App](./docs/github-app.md).
This should probably be a _different_ app than the one used for testing.

### Deploy Interpersonal

Interpersonal is a pretty standard Flask app.

First, write a config file somewhere.
See `dev.config.yml` for an example.
To create a good cookie secret, run something like:

```sh
python3 -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())'
```

Create a virtual environment somewhere and install dependencies,
then configure the app:

```sh
python3 -m venv /path/to/interpersonal.venv
. /path/to/interpersonal.venv/bin/activate

cd /path/to/interpersonal-git-repo
pip install -e .

export INTERPERSONAL_CONFIG=/path/to/interpersonal.config.yml
export FLASK_APP=interpersonal

flask init-db

# Make note of this secret key, it is used in apache config later
echo "$INTERPERSONAL_COOKIE_SECRET_KEY"
```

Then create a WSGI file.
Note that you must hard-code the config path.
(You might think that you can instead use environment variables
with Apache's `SetEnv`, but this doesn't work:
<https://stackoverflow.com/questions/9016504/apache-setenv-not-working-as-expected-with-mod-wsgi>.)

```py
from interpersonal import create_app
application = create_app(configpath="/path/to/interpersonal.config.yml")
```

Finally, configure Apache to call the WSGI file:

```apache
<VirtualHost *>
    ServerName example.com

    WSGIDaemonProcess interpersonal user=user1 group=group1 threads=5 \
        python-home=/path/to/interpersonal.venv
    WSGIScriptAlias / /var/www/interpersonal/interpersonal.wsgi.py

    <Directory /var/www/interpersonal>
        WSGIProcessGroup interpersonal
        WSGIApplicationGroup %{GLOBAL}
        Order deny,allow
        Allow from all
    </Directory>
</VirtualHost>
```

## How to use this to authenticate to an application that understands IndieAuth?

* Deploy it for production (per above) and note the URI, like `interpersonal.example.com`.
* On your own website at your own domain, add a link with the appropriate `rel` attribute, like
  `<link rel="authorization_endpoint" href="https://interpersonal.example.com/indieauth/authorize">`
