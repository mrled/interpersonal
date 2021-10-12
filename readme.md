# Interpersonal

The connection between my little site and the Indie Web.

## Implementation

This code benefitted greatly from <https://unrelenting.technology>'s
[Sellout Engine](https://github.com/unrelentingtech/sellout),
and also from the [Flask tutorial](https://flask.palletsprojects.com/en/2.0.x/tutorial/).

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

```sh

export INTERPERSONAL_DATABASE="dev.db"
export INTERPERSONAL_COOKIE_SECRET_KEY="any value is ok in dev"
export FLASK_APP=interpersonal
flask init-db  # Initialize the database
flask set-login-password YOUR-NEW-PASSWORD  # Allow logging in locally
flask set-owner-profile http://you.example.org/  # Set the owner profile
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

## Production

Interpersonal is a pretty standard Flask app.
Create a virtual environment somewhere and install dependencies,
then configure the app:

```sh
python3 -m venv /path/to/interpersonal.venv
. /path/to/interpersonal.venv/bin/activate

cd /path/to/interpersonal-git-repo
pip install -e .

export INTERPERSONAL_DATABASE="/path/to/interpersonal.db"
export INTERPERSONAL_COOKIE_SECRET_KEY="$(python3 -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())')"
export FLASK_APP=interpersonal

flask init-db
flask set-login-password YOUR-NEW-PASSWORD
flask set-owner-profile YOUR-REAL-INDIEWEB-PROFILE-URI

# Make note of this secret key, it is used in apache config later
echo "$INTERPERSONAL_COOKIE_SECRET_KEY"
```

Then create a WSGI file.
Note that you must hard-code the database path and cookie key.
(You might think that you can instead use environment variables
with Apache's `SetEnv`, but this doesn't work:
<https://stackoverflow.com/questions/9016504/apache-setenv-not-working-as-expected-with-mod-wsgi>.)

```py
from interpersonal import create_app
application = create_app(
    dbpath="/path/to/interpersonal.db",
    cookey="your-generated-value-previously",
    loglevel="DEBUG", # optional
)
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

## Tokens and codes and secrets

There are a few different kinds of unguessable ("secret") blobs of data,
all of which might easily be termed "tokens" or "codes" or "secrets".

* The login password: This is entered by the user (me) to log in.
    I am the only user for this site, so I don't have a 'users' table containing this value;
    instead I have a singular 'login_password' value in the AppSettings table,
    and I present only a password entry box on the login page.
* The authorization code: Generated by `indieauth.grant()`,
    this value is created from random data when the user logs in and authorizes a given app.
    It is stored in the `AuthorizationCode` table.
    Defined by the IndieAuth spec.
    Sellout Engine prefixes these values with `C-`.
* The bearer token: The application exchanges its authorization code for one of these.
    The exchange happens in `indieauth.bearer()`.
    Also created from random data.
    Stored in the `BearerToken` table.
    (I'm not really issuiing bearer tokens yet, but I will eventually.)
    Defined by the IndieAuth spec.
    Sellout Engine prefixes these values with `B-`.

## How to use this to authenticate to an application that understands IndieAuth?

* Deploy it for production (per above) and note the URI, like `interpersonal.example.com`.
* On your own website at your own domain, add a link with the appropriate `rel` attribute, like
    `   <link rel="authorization_endpoint" href="https://interpersonal.example.com/indieauth/authorize">`
