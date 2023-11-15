FROM python:3-alpine

# Dependencies
RUN pip --no-cache-dir install \
        "click>=7.0" \
        "PyYAML>=5.1" \
        "jsonref>=0.2.0"

# Application
COPY . /src
RUN pip --no-cache-dir install /src && rm -rf /src

WORKDIR /out
ENTRYPOINT ["/usr/local/bin/openapi2jsonschema"]
CMD ["--help"]
