# The plugin's image: the SDK's base for the release pyproject.toml pins, the
# wrapper, and the desk's front end built beside it (web/, which
# open-meridian/ci/frontend.sh writes before an upload, with the notices of
# every package it ships).
ARG BASE=ghcr.io/open-meridian/plugin-python:0.37.1@sha256:cb612e16262390c5dc71ee976731bd74d2c693455aef788ab36fcfd3d16291c2
FROM ${BASE}
WORKDIR /plugin
COPY . .
RUN test -s web/index.html && test -s web/NOTICES.txt && pip install --no-cache-dir .
USER 65532
CMD ["desk"]
