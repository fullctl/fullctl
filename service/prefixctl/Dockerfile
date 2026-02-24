ARG base_repo=python
ARG base_tag=3.11-alpine
ARG builder_repo=ghcr.io/fullctl/fullctl-builder-alpine
ARG builder_tag=main

ARG virtual_env=/venv
ARG install_to=/srv/service
ARG build_deps=""
ARG extra_pip_install_dir=""

ARG run_deps=" \
    libgcc \
    postgresql-libs \
    "
ARG uid=6300
ARG user=fullctl
ARG service_dir=service/prefixctl

FROM ${base_repo}:${base_tag} as base

ARG virtual_env
ARG install_to

ENV SERVICE_HOME=$install_to
ENV VIRTUAL_ENV=$virtual_env
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


# build container
FROM $builder_repo:$builder_tag as builder

ARG extra_pip_install_dir
ARG service_dir

# For monorepo: copy fullctl source for path dependency resolution
COPY pyproject.toml poetry.lock README.md ./
COPY src/ src/

# Set workdir to service directory (path = "../.." resolves to builder workdir)
WORKDIR ${service_dir}

# Copy service files
COPY ${service_dir}/pyproject.toml ${service_dir}/poetry.lock ./

# Need to upgrade pip and wheel within Poetry for all its installs
RUN poetry install --no-root && pip install /build

# gitignore is just a placeholder for if extra is empty
COPY ${service_dir}/.gitignore $extra_pip_install_dir ./plugins/
RUN test -z "$extra_pip_install_dir" || pip install plugins/*.tar.gz

COPY ${service_dir}/Ctl/VERSION Ctl/

#### final image

FROM base as final

ARG service_dir
ARG run_deps
ARG run_dirs="locale media static"
ARG uid
ARG user

# extra settings file if needed
# TODO keep in until final production deploy
ARG COPY_SETTINGS_FILE=mainsite/settings/dev.py

# add dependencies
RUN apk --update --no-cache add $run_deps

RUN adduser -Du $uid $user

WORKDIR $SERVICE_HOME
COPY --from=builder "$VIRTUAL_ENV" "$VIRTUAL_ENV"

RUN mkdir -p etc $run_dirs
COPY ${service_dir}/Ctl/VERSION etc/
COPY ${service_dir}/docs/ docs

RUN chown -R $uid:$uid $run_dirs

#### entry point from final image, not tester
FROM final

ARG uid
ARG service_dir

COPY ${service_dir}/src/ main/
COPY ${service_dir}/Ctl/docker/entrypoint.sh .
RUN ln -s $SERVICE_HOME/entrypoint.sh /entrypoint
RUN ln -s /venv $SERVICE_HOME/venv

COPY ${service_dir}/Ctl/docker/django-uwsgi.ini etc/
COPY ${service_dir}/Ctl/docker/manage.sh /usr/bin/manage

#ENV UWSGI_SOCKET=127.0.0.1:6002

USER $uid

ENTRYPOINT ["/entrypoint"]
CMD ["runserver"]
