FROM python:3-alpine
MAINTAINER Yann Hamon "yann@mandragor.org"

COPY . /src
RUN cd src && pip install -e .

WORKDIR /out

ENTRYPOINT ["/usr/local/bin/openapi2jsonschema"]
CMD ["--help"]
