# Notes on fast.ai's ghapi Python module

I use [GhApi](https://ghapi.fast.ai) to talk to Github.

## JWT tokens for authenticating as an app

Currently jwt tokens don't work properly in any released version:
<https://github.com/fastai/ghapi/issues/85>,
but it is supposed to be fixed as of
<https://github.com/fastai/ghapi/pull/88>.

You can tell pip to use a certain commit, rather than a certain released version,
with something like this in setup.py:

```python3
setuptools.setup(
    install_requires=[
        "ghapi @ git+ssh://git@github.com/fastai/ghapi@d8fb5c2#egg=ghapi",
        ...
    ],
    ...
```

However, that didn't solve my problem either.
Github keeps telling me my credentials are not correct.

For now I'm working around this.

Some useful code for comparison:
<https://github.com/ffalor/flask-githubapplication/blob/main/src/flask_githubapplication/core.py>

## Debugging

Print information about each request:
<https://ghapi.fast.ai/core.html#print_summary>
