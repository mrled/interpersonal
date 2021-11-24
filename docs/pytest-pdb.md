# pytest and pdb

It's useful to run pytest with `--pdb`, so that it automatically opens the debugger on an uncaught exception.

You can also sprinkle your code with `import pdb; pdb.set_trace()`.

If you need to configure pdb, you might do that with `import pdb; pdb.Pdb(skip=["modname.*"]).set_trace()` as descripted in the [pdb documentation](https://docs.python.org/3/library/pdb.html). If you do this, make sure to run pytest with `--capture=no`, or else it will capture stdin/stdout from the debugger and you will not be able to interact with it.
