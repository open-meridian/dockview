# The desk's front end, built in a container, so a person building the plugin
# needs Docker and nothing else: the pinned packages installed from
# web/package-lock.json, type-checked and bundled (web/build.mjs); then the
# notices of every package it ships, refused if any is under a GPL-family
# licence or is dockview-enterprise (notices.mjs); and the files bundled
# (web/bundled.json) searched for dockview-enterprise. Any of these failing
# fails the build, and nothing is written.
#
# Built from the repository's root by open-meridian/ci/frontend.sh, which
# exports the last stage, the built files alone, into open-meridian/plugin/web.
# Each COPY names what it takes, so nothing else of the repository (nor a
# node_modules left beside the sources) enters the build.
ARG NODE=node:26.12.1-trixie-slim@sha256:94816674c62774da0d099a947bf4613b9e1972a2733abd0d0cd80e795f8411d0

FROM ${NODE} AS build
WORKDIR /src/open-meridian/web
COPY open-meridian/web/package.json open-meridian/web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts --no-audit --no-fund
COPY open-meridian/web/tsconfig.json open-meridian/web/build.mjs open-meridian/web/index.html open-meridian/web/popout.html ./
COPY open-meridian/web/src ./src
COPY open-meridian/ci/notices.mjs ../ci/notices.mjs
RUN node node_modules/typescript/bin/tsc -p . && node build.mjs
RUN node ../ci/notices.mjs . ../plugin/web/NOTICES.txt
# Only dockview-core's own error text names dockview-enterprise; no file of it
# is installed or bundled.
RUN if [ -e node_modules/dockview-enterprise ] || grep -n 'dockview-enterprise' bundled.json; then \
      echo "frontend: dockview-enterprise is installed or bundled" >&2; exit 1; \
    fi

FROM scratch
COPY --from=build /src/open-meridian/plugin/web/ /
