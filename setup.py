import setuptools

with open("readme.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name="interpersonal",
    version="0.0.1",
    author="Micah R Ledbetter",
    author_email="me@micahrl.com",
    description="The connection between my little site and the Indie Web.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mrled/psyops/",
    packages=["interpersonal"],
    python_requires=">=3.6",
    include_package_data=True,
    install_requires=[
        "coverage",
        "cryptography",
        "flask",
        "pytest",
        "rfc3986",
    ],
)
