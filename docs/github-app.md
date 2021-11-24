# Github app

For Github support, you must create a Github app.
In short:

- <https://github.com/settings/apps/new>
- App name: I use the domain name it's hosted at, which for me is <interpersonal.micahrl.com>
- Desription: "Interpersonal connects static sites to the indie web"
- Homepage URL: include the https, like <https://interpersonal.micahrl.com>
- Callback URL: Should be `/micropub/authorized/github` for your base domain, for instance <https://interpersonal.micahrl.com/micropub/authorized/github>
- Expire user authorization tokens: checked
- Request user authorization (OAuth) during installation: checked
- Post installation: Redirect on update: checked
- Permissions:
    - Repository permissions: Contents: Read & write
- Where can this GitHub App be installed? `Only on this account`
- Then click create.

Once the app is created, you can find or generate a few important bits of information:

- Then you have to add a **client secret**; save that somewhere safe.
- After that you'll have to "generate a **private key**", and save the resulting `.pem` file somewhere safe.
- Make note of the **app id**, which is a number.

Finally, note that the app currently is not "installed", and has no rights to any repositories.
To install it:

- Click "install app" in the left side bar, then the green "Install" button
- You can grant access to all repos, but better to just grant to the select repos you need
- Then it redirects you to `/micropub/authorized/github`
    - real example: `https://interpersonal.micahrl.com/micropub/authorized/github?code=5b960779a00b4e2d4ba0&installation_id=20836900&setup_action=install`
    - The `code` is used for TODO FIXME
    - `installation_id`: a unique identifier for the installation of this app to this specific Github account.
        - Required for access to any of the repositories that this app has access to.
        - You can retrieve it from the API later via
          [`/app/installations`](https://docs.github.com/en/rest/reference/apps#list-installations-for-the-authenticated-app)
