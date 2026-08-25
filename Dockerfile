# FullCtl builder image (repository pinned fullctl/fullctl), built by
# `scripts/build.py builder` from the monorepo root and consumed by
# Dockerfile.service as its builder stage base.
#
# Base image: oraclelinux:9-slim-fips. Slim OL9 ships no Python, so
# python3.11 + python3.11-devel and the build toolchain are installed via
# microdnf (uwsgi builds from sdist and needs the interpreter headers).
# Dependency management is uv only.
#
# FIPS note: md5 usages in application code need usedforsecurity=False
# (supported by OL9 python3.11) -- flagged for real-build validation, see
# docs/build.md.

ARG base_repo=oraclelinux
ARG base_tag=9-slim-fips
ARG python_ver=3.11
ARG virtual_env=/venv
ARG uv_tag=latest

ARG build_deps=" \
    gcc \
    gcc-c++ \
    make \
    git \
    libffi-devel \
    libjpeg-turbo-devel \
    libpq-devel \
    openssl-devel \
    "

FROM ghcr.io/astral-sh/uv:${uv_tag} AS uv

FROM ${base_repo}:${base_tag} AS base

ARG virtual_env

# env to pass to sub images
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=$virtual_env
ENV UV_PROJECT_ENVIRONMENT=$virtual_env
ENV UV_PYTHON_DOWNLOADS=never
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# build container
FROM base AS builder

ARG build_deps
ARG python_ver
ARG virtual_env

RUN microdnf install -y python${python_ver} python${python_ver}-devel $build_deps \
    && microdnf clean all

# ship uv
COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /build

# individual files here instead of COPY . . for caching
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# pre-build the core library venv (dependencies only, from the root lock);
# Dockerfile.service syncs the per-service workspace member on top of this
RUN uv venv "$VIRTUAL_ENV" --python "python${python_ver}" \
    && uv sync --frozen --no-install-project --no-editable
