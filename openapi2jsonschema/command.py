#!/usr/bin/env python3

import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import click
import yaml
from jsonref import JsonRef

from openapi2jsonschema.errors import UnsupportedError
from openapi2jsonschema.log import debug, error, info
from openapi2jsonschema.util import (
    additional_properties,
    allow_null_optional_fields,
    append_no_duplicates,
    change_dict_values,
    replace_int_or_string,
)


@click.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False, writable=True, resolve_path=True, path_type=Path),
    default="schemas",
    metavar="PATH",
    help="Directory to store schema files",
)
@click.option(
    "-p",
    "--prefix",
    default="_definitions.json",
    help="Prefix for JSON references (only for OpenAPI versions before 3.0)",
)
@click.option(
    "--stand-alone", is_flag=True, help="Whether or not to de-reference JSON schemas"
)
@click.option(
    "--expanded", is_flag=True, help="Expand Kubernetes schemas by API version"
)
@click.option(
    "--kubernetes", is_flag=True, help="Enable Kubernetes specific processors"
)
@click.option(
    "--strict",
    is_flag=True,
    help="Prohibits properties not in the schema (additionalProperties: false)",
)
@click.argument("schema", metavar="SCHEMA_URL")
def default(output: Path, schema, prefix, stand_alone, expanded, kubernetes, strict):
    """
    Converts a valid OpenAPI specification into a set of JSON Schema files
    """
    info("Downloading schema")
    if not urlparse(schema).scheme or Path(schema).is_file():
        schema = Path(schema).resolve().as_uri()
    req = urllib.request.Request(schema)
    response = urllib.request.urlopen(req)

    info("Parsing schema")
    # Note that JSON is valid YAML, so we can use the YAML parser whether
    # the schema is stored in JSON or YAML
    data = yaml.load(response.read(), Loader=yaml.SafeLoader)

    if "swagger" in data:
        version = data["swagger"]
    elif "openapi" in data:
        version = data["openapi"]
    else:
        raise ValueError(
            "cannot convert data to JSON because we could not find 'openapi' or 'swagger' keys"
        )

    output.mkdir(parents=True, exist_ok=True)

    if version < "3":
        info("Generating shared definitions")
        definitions = data["definitions"]
        if kubernetes:
            definitions["io.k8s.apimachinery.pkg.util.intstr.IntOrString"] = {
                "oneOf": [{"type": "string"}, {"type": "integer"}]
            }
            # Although the kubernetes api does not allow `number`  as valid
            # Quantity type - almost all kubenetes tooling
            # recognizes it is valid. For this reason, we extend the API definition to
            # allow `number` values.
            definitions["io.k8s.apimachinery.pkg.api.resource.Quantity"] = {
                "oneOf": [{"type": "string"}, {"type": "number"}]
            }

            # For Kubernetes, populate `apiVersion` and `kind` properties from `x-kubernetes-group-version-kind`
            for type_name in definitions:
                type_def = definitions[type_name]
                if "properties" not in type_def:
                    error(f"{type_name} has no properties")
                    continue

                if "x-kubernetes-group-version-kind" in type_def:
                    for kube_ext in type_def["x-kubernetes-group-version-kind"]:
                        if "apiVersion" in type_def["properties"]:
                            api_version = (
                                kube_ext["group"] + "/" + kube_ext["version"]
                                if kube_ext["group"]
                                else kube_ext["version"]
                            )
                            append_no_duplicates(
                                type_def["properties"]["apiVersion"],
                                "enum",
                                api_version,
                            )
                        if "kind" in type_def["properties"]:
                            kind = kube_ext["kind"]
                            append_no_duplicates(
                                type_def["properties"]["kind"], "enum", kind
                            )
        if strict:
            definitions = additional_properties(definitions)
        with output.joinpath("_definitions.json").open("w") as definitions_file:
            json.dump({"definitions": definitions}, definitions_file, indent=2)

    types = []

    info("Generating individual schemas")
    if version < "3":
        components = data["definitions"]
    else:
        components = data["components"]["schemas"]

    for title in components:
        kind = title.split(".")[-1]
        if kubernetes:
            try:
                group = title.split(".")[-3].lower()
                api_version = title.split(".")[-2].lower()
            except IndexError:
                error(f"unable to determine group and apiversion from {title}")
                continue
        specification = components[title]
        specification["$schema"] = "http://json-schema.org/schema#"
        specification.setdefault("type", "object")

        if strict:
            specification["additionalProperties"] = False

        if kubernetes and expanded:
            if group in ["core", "api"]:
                full_name = "%s-%s" % (kind, api_version)
            else:
                full_name = "%s-%s-%s" % (kind, group, api_version)
        else:
            full_name = kind

        types.append(title)

        try:
            debug("Processing %s" % full_name)

            # These APIs are all deprecated
            if kubernetes:
                if title.split(".")[3] == "pkg" and title.split(".")[2] == "kubernetes":
                    raise UnsupportedError(
                        "%s not currently supported, due to use of pkg namespace"
                        % title
                    )

            # This list of Kubernetes types carry around jsonschema for Kubernetes and don't
            # currently work with openapi2jsonschema
            if (
                kubernetes
                and stand_alone
                and kind.lower()
                in [
                    "jsonschemaprops",
                    "jsonschemapropsorarray",
                    "customresourcevalidation",
                    "customresourcedefinition",
                    "customresourcedefinitionspec",
                    "customresourcedefinitionlist",
                    "customresourcedefinitionspec",
                    "jsonschemapropsorstringarray",
                    "jsonschemapropsorbool",
                ]
            ):
                raise UnsupportedError("%s not currently supported" % kind)

            updated = change_dict_values(specification, prefix, version)
            specification = updated

            if stand_alone:
                base = f"{output.as_uri()}/"
                specification = JsonRef.replace_refs(specification, base_uri=base)

            if "additionalProperties" in specification:
                if specification["additionalProperties"]:
                    updated = change_dict_values(
                        specification["additionalProperties"], prefix, version
                    )
                    specification["additionalProperties"] = updated

            if strict and "properties" in specification:
                updated = additional_properties(specification["properties"])
                specification["properties"] = updated

            if kubernetes and "properties" in specification:
                updated = replace_int_or_string(specification["properties"])
                updated = allow_null_optional_fields(updated)
                specification["properties"] = updated

            debug("Generating %s.json" % full_name)
            with output.joinpath(f"{full_name}.json").open("w") as schema_file:
                json.dump(specification, schema_file, indent=2)
        except Exception as e:
            error("An error occured processing %s: %s" % (kind, e))

    info("Generating schema for all types")
    contents = {"oneOf": []}
    for title in types:
        if version < "3":
            contents["oneOf"].append({"$ref": "%s#/definitions/%s" % (prefix, title)})
        else:
            contents["oneOf"].append(
                {"$ref": (title.replace("#/components/schemas/", "") + ".json")}
            )
    with output.joinpath("all.json").open("w") as all_file:
        json.dump(contents, all_file, indent=2)


if __name__ == "__main__":
    default()
