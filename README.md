# openapi2jsonschema

A utility to extract [JSON Schema](http://json-schema.org/) from a
valid [OpenAPI](https://www.openapis.org/) specification.

## Why

OpenAPI contains a list of type `definitions` using a superset of JSON
Schema. These are used internally by various OpenAPI compatible tools. I
found myself however wanting to use those schemas separately, outside
existing OpenAPI tooling. Generating separate schemas for types defined
in OpenAPI allows for all sorts of indepent tooling to be build which
can be easily maintained, because the canonical definition is shared.

## Installation

`openapi2jsonschema` is implemented in Python. Assuming you have a
Python intepreter and pip installed you should be able to install with:

```
pip install git+https://github.com/stasjok/openapi2jsonschema.git
```

With podman/docker:

```
podman build -t openapi2jsonschema https://github.com/stasjok/openapi2jsonschema.git
```

With nix:

```
nix profile install github:stasjok/openapi2jsonschema#openapi2jsonschema
```

This has not yet been widely tested and is currently in a _works on my
machine_ state.

## Usage

The simplest usage is to point the `openapi2jsonschema` tool at a URL
containing a JSON (or YAML) OpenAPI definition like so:

```
openapi2jsonschema https://raw.githubusercontent.com/kubernetes/kubernetes/master/api/openapi-spec/swagger.json
```

This will generate a set of schemas in a `schemas` directory. The tool
provides a number of options to modify the output:

```
$ openapi2jsonschema --help
Usage: openapi2jsonschema [OPTIONS] SCHEMA_URL

  Converts a valid OpenAPI specification into a set of JSON Schema files

Options:
  -o, --output PATH  Directory to store schema files
  -p, --prefix TEXT  Prefix for JSON references (only for OpenAPI versions
                     before 3.0)
  --stand-alone      Whether or not to de-reference JSON schemas
  --expanded         Expand Kubernetes schemas by API version
  --kubernetes       Enable Kubernetes specific processors
  --strict           Prohibits properties not in the schema
                     (additionalProperties: false)
  --only-top-level   Output schemas only with a 'kind' and 'apiVersion'
                     properties (only for kubernetes)
  --help             Show this message and exit.
```

A second tool `kube2jsonschema` will download openapi schema directly from Kubernetes.
It has the same flags, except `--kubernetes` is implied.

## Example

My specific usecase is to use Kubernetes json-schema in `yaml-language-server`.
Note that yaml-language-server need a special handling for Kubernetes.
By default, it works correctly only with a hard-coded json-schema.
You can try my patch here: <https://github.com/stasjok/yaml-language-server/tree/custom-kube-schema-url>.
With this patch you can set in settings:

```json
{
  "yaml": {
    "kubernetesSchemaUrl": "/path/to/schemas/all.json",
    "schemas": {
      "kubernetes": [
        "*.yml"
      ]
    }
  }
}
```

To generate json-schemas run (you need a working kubectl):

```
kube2jsonschema -o /path/to/schemas/ --strict
```
