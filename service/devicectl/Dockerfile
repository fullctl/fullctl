ARG base_repo=python
ARG base_tag=3.11-alpine
ARG builder_repo=ghcr.io/fullctl/fullctl-builder-alpine
ARG builder_tag=prep-release

ARG virtual_env=/venv
ARG install_to=/srv/service
ARG build_deps=""
ARG run_deps=" \
    libgcc \
    postgresql-libs \
    rrdtool-dev \
    libstdc++ \
    "
# XXX ARG extra_pip_install
ARG uid=6300
ARG user=fullctl

FROM ${base_repo}:${base_tag} as base

ARG virtual_env
ARG install_to
ARG build_deps
ARG run_deps

ENV SERVICE_HOME=$install_to
ENV VIRTUAL_ENV=$virtual_env
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


# build container
FROM $builder_repo:$builder_tag as builder

ARG extra_pip_install_dir

# individual files here instead of COPY . . for caching
COPY pyproject.toml poetry.lock $extra_pip_install_dir ./

# Need to upgrade pip and wheel within Poetry for all its installs
RUN apk add rrdtool-dev
RUN poetry install --no-root

# Cant be in poetry because that fails to install unless rrdtool
# is installed in the system, so it breaks github CI for linting and stuff
RUN pip install rrdtool

RUN test -z "$extra_pip_install_dir" || pip install *.tar.gz

COPY Ctl/VERSION Ctl/

#### final image

FROM base as final

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
COPY Ctl/VERSION etc/
COPY docs/ docs
COPY fixtures/ fixtures

RUN chown -R $uid:$uid $run_dirs

#### entry point from final image, not tester
FROM final

ARG uid

COPY src/ main/
COPY Ctl/docker/entrypoint.sh .
RUN ln -s $SERVICE_HOME/entrypoint.sh /entrypoint
RUN ln -s /venv $SERVICE_HOME/venv

COPY Ctl/docker/django-uwsgi.ini etc/
COPY Ctl/docker/manage.sh /usr/bin/manage

#ENV UWSGI_SOCKET=127.0.0.1:6002

USER $uid

ENTRYPOINT ["/entrypoint"]
CMD ["runserver"]
