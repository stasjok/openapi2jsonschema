from setuptools import setup

setup(
    name="openapi2jsonschema",
    version="0.9.0",
    description="OpenAPI to JSON schemas converter",
    long_description="Converts OpenAPI definitions into JSON schemas for all types in the API",
    author="Gareth Rushgrove",
    author_email="gareth@morethanseven.net",
    maintainer="Stanislav Asunkin",
    license="Apache-2.0",
    keywords=["openapi", "jsonschema"],
    url="https://github.com/stasjok/openapi2jsonschema",
    packages=["openapi2jsonschema"],
    install_requires=[
        "click >= 7.0",
        "PyYAML >= 5.1",
        "jsonref >= 0.2.0",
    ],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "openapi2jsonschema = openapi2jsonschema.command:default",
        ]
    },
)
