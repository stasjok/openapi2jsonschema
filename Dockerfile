FROM python:3-alpine

COPY . /src
RUN pip --no-cache-dir install /src && rm -rf /src

WORKDIR /out

ENTRYPOINT ["/usr/local/bin/openapi2jsonschema"]
CMD ["--help"]
