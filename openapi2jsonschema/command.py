#!/usr/bin/env python3

import json
import urllib.request
from pathlib import Path
from typing import Dict, Optional, cast
from urllib.parse import urlparse

import click
import kubernetes
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


def process(
    data,
    output: Path,
    prefix: str,
    stand_alone: bool,
    expanded: bool,
    kubernetes: bool,
    strict: bool,
):
    """
    Converts a valid OpenAPI specification into a set of JSON Schema files
    """
    version = data.get("swagger") or data.get("openapi")
    if not version:
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
            for type_name, type_def in definitions.items():
                if "properties" not in type_def:
                    error(f"{type_name} has no properties")
                    continue

                for kube_ext in type_def.get("x-kubernetes-group-version-kind", []):
                    if "apiVersion" in type_def["properties"]:
                        api_version = "/".join(
                            filter(None, [kube_ext["group"], kube_ext["version"]])
                        )
                        append_no_duplicates(
                            type_def["properties"]["apiVersion"],
                            "enum",
                            api_version,
                        )
                    if "kind" in type_def["properties"]:
                        append_no_duplicates(
                            type_def["properties"]["kind"], "enum", kube_ext["kind"]
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

    for title, specification in components.items():
        title_splitted = title.split(".")
        kind = title_splitted[-1]
        full_name = kind
        if kubernetes and expanded:
            try:
                group = title_splitted[-3].lower()
                api_version = title_splitted[-2].lower()
            except IndexError:
                error(f"unable to determine group and apiversion from {title}")
                continue
            full_name = (
                f"{kind}-{api_version}"
                if group in ["core", "api"]
                else f"{kind}-{group}-{api_version}"
            )

        specification["$schema"] = "http://json-schema.org/schema#"
        specification.setdefault("type", "object")

        if strict:
            specification["additionalProperties"] = False

        types.append(title)

        try:
            debug(f"Processing {full_name}")

            # These APIs are all deprecated
            if kubernetes:
                if title_splitted[3] == "pkg" and title_splitted[2] == "kubernetes":
                    raise UnsupportedError(
                        f"{title} not currently supported, due to use of pkg namespace"
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
                raise UnsupportedError(f"{kind} not currently supported")

            updated = change_dict_values(specification, prefix, version)
            specification = updated

            if stand_alone:
                base = f"{output.as_uri()}/"
                specification = JsonRef.replace_refs(specification, base_uri=base)
                # Make type checker happy, cast to unknown dict
                specification = cast(Dict, specification)

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

            debug(f"Generating {full_name}.json")
            with output.joinpath(f"{full_name}.json").open("w") as schema_file:
                json.dump(specification, schema_file, indent=2)
        except Exception as e:
            error(f"An error occured processing {kind}: {e}")

    info("Generating schema for all types")
    contents = {"oneOf": []}
    for title in types:
        if version < "3":
            contents["oneOf"].append({"$ref": f"{prefix}#/definitions/{title}"})
        else:
            contents["oneOf"].append(
                {"$ref": title.replace("#/components/schemas/", "") + ".json"}
            )
    with output.joinpath("all.json").open("w") as all_file:
        json.dump(contents, all_file, indent=2)


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
def default(
    output: Path,
    prefix: str,
    stand_alone: bool,
    expanded: bool,
    kubernetes: bool,
    strict: bool,
    schema: str,
):
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

    process(data, output, prefix, stand_alone, expanded, kubernetes, strict)


@click.command()
@click.option("--kubeconfig", help="Path to the kubeconfig file")
@click.option("--context", help="The name of the kubeconfig context to use")
@click.option(
    "--insecure-skip-tls-verify",
    "insecure",
    is_flag=True,
    help="If set, the server's certificate will not be checked for validity."
    " This will make your HTTPS connections insecure",
)
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
    help="Prefix for JSON references",
)
@click.option(
    "--stand-alone", is_flag=True, help="Whether or not to de-reference JSON schemas"
)
@click.option("--expanded", is_flag=True, help="Expand schemas by API version")
@click.option(
    "--strict",
    is_flag=True,
    help="Prohibits properties not in the schema (additionalProperties: false)",
)
def kube(
    kubeconfig: Optional[str],
    context: Optional[str],
    insecure: bool,
    output: Path,
    prefix: str,
    stand_alone: bool,
    expanded: bool,
    strict: bool,
):
    """
    Loads an OpenAPI specification from Kubernetes and converts it into a set of JSON Schema files
    """
    info("Reading kubeconfig")
    configuration = kubernetes.client.Configuration()
    kubernetes.config.load_kube_config(
        config_file=kubeconfig, context=context, client_configuration=configuration
    )
    if insecure:
        configuration.verify_ssl = False

    with kubernetes.client.ApiClient(configuration=configuration) as api_client:
        info("Getting schema")
        data = api_client.call_api(
            "/openapi/v2",
            "GET",
            _return_http_data_only=True,
            auth_settings=["BearerToken"],
            response_type=object,
        )
    process(data, output, prefix, stand_alone, expanded, True, strict)


if __name__ == "__main__":
    default()
