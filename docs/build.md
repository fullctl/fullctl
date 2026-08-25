# Building Images

The monorepo owns its docker image builds. All repo-intrinsic build logic —
service resolution, build manifests, Dockerfiles, docker invocation — lives
here; environment-intrinsic logic (registries, tag/vtag computation, plugin
fetching, overlay images, helm values, deploy) stays in fci0, which delegates
to the entrypoint described below and consumes its JSON output.

This document is the build contract. Anything that builds monorepo images
(fci0, CI, a developer shell) goes through `scripts/build.py`.

## Build Entrypoint: `scripts/build.py`

A self-contained script (PEP 723 inline metadata for PyYAML) run with uv:

```sh
uv run scripts/build.py builder --registry REG --tag TAG [--push]
uv run scripts/build.py service NAME --registry REG --tag TAG
    [--push] [--builder-repo R] [--builder-tag T]
    [--image-suffix SFX] [--extra-pip-install-dir RELPATH] [--no-tasks]
```

### `builder` subcommand

Builds the root builder image from the root `Dockerfile`. Its repository name
is pinned `fullctl/fullctl` — the resulting ref is `REG/fullctl/fullctl:TAG`.

| Flag | Required | Description |
|---|---|---|
| `--registry` | yes | image registry the ref is composed against |
| `--tag` | yes | image tag |
| `--push` | no | `docker push` the image after building |

### `service` subcommand

Builds a service image (and, when present, its tasks image — see
[Tasks Images](#tasks-images)).

The service path is resolved in fci0's order: `private/<name>/` first, then
`service/<name>/`. `service fullctl` is rejected — the core library has no
service image; use the `builder` subcommand instead.

The service's `Ctl/docker.yaml` manifest is loaded and validated (see
[Manifest Schema](#per-service-manifest-ctldockeryaml)), then `docker build`
runs with the repo root as context, `-f Dockerfile.service`, and the
manifest-derived `--build-arg`s.

| Flag | Required | Description |
|---|---|---|
| `NAME` (positional) | yes | service name (e.g. `ixctl`) |
| `--registry` | yes | image registry |
| `--tag` | yes | image tag |
| `--push` | no | push every built ref after building |
| `--builder-repo` | no (warns) | builder image repository (`builder_repo` build arg; default `fullctl/fullctl`) |
| `--builder-tag` | no | builder image tag (`builder_tag` build arg; default `latest`) |
| `--image-suffix` | no | suffix appended to the repository name: `fullctl/<name><sfx>` |
| `--extra-pip-install-dir` | no | repo-relative directory of plugin sdists to `uv pip install` into the venv |
| `--no-tasks` | no | skip the tasks image even if `Ctl/docker/Dockerfile.tasks` exists |

#### `--builder-repo` semantics

`Dockerfile.service` resolves its builder stage from
`FROM ${builder_repo}:${builder_tag}`, so `--builder-repo` must be the
**registry-qualified** repository of the builder you intend to consume — e.g.
`localhost:5000/fullctl/fullctl`, not `fullctl/fullctl`. An unqualified value
resolves against Docker Hub and silently builds against a foreign or stale
image rather than the builder just built by `scripts/build.py builder`.

The flag is optional only so that it stays out of fci0's way (fci0 always
passes it); omitting it prints a warning to stderr and leaves the
`fullctl/fullctl:latest` Docker Hub default in place. Treat it as required
for any hand-run build.

#### `--image-suffix` semantics

The suffix is appended to the *repository name*, not the tag:

```
--image-suffix -fl   →  REG/fullctl/ixctl-fl:TAG
```

fci0 uses this for vtag-decorated plugin-augmented base images
(`fullctl/<svc>-<vtag>`). The tasks image inherits the suffix before its own
`-tasks` suffix: `REG/fullctl/ixctl-fl-tasks:TAG`. Suffixes typically start
with `-`; the entrypoint handles that (a leading `-` is not mistaken for an
option). A value is still required: a following token that starts with `--`,
or no following token at all, is an error rather than a silently swallowed
flag.

### Output: JSON on the last stdout line

Docker's build output interleaves on stdout. The built image refs are printed
as a single JSON object on the **last stdout line**; consumers must parse the
last line only.

```json
{"service": "reg/fullctl/ixctl:1.2.3", "tasks": "reg/fullctl/ixctl-tasks:1.2.3"}
```

- `builder` prints `{"builder": "reg/fullctl/fullctl:1.2.3"}`
- `service` prints `{"service": ...}` plus `{"tasks": ...}` when a tasks image
  was built

### Errors and exit behavior

The entrypoint fails fast with exit code 1 and a single-line message on
stderr (`error: ... (see docs/build.md)`) naming the offending file, on any
of:

- missing manifest (`Ctl/docker.yaml` not found)
- malformed YAML or a missing `docker:` mapping
- unknown manifest keys
- wrong/missing `schema` value
- wrong value types (`build_deps`/`run_deps`/`repos` must be lists of
  strings, `cmd` a string)
- unresolvable service name, or `service fullctl`
- missing Dockerfile
- non-zero exit from any `docker build`/`docker push`

Nothing is printed on the last stdout line in the error case — consumers
(fci0) surface stderr verbatim and abort the service build.

## Per-Service Manifest: `Ctl/docker.yaml`

Every buildable service carries `<service_path>/Ctl/docker.yaml` (schema 1):

```yaml
docker:
  schema: 1
  repos: [ol9_codeready_builder]  # dnf repositories to enable; default: []
  build_deps: [rust, cargo]   # extra builder-stage packages; default: []
  run_deps: [libgcc, libpq]   # runtime packages; default: [libgcc, libpq]
  cmd: runserver              # default container command; default: runserver
```

Rules:

- `schema: 1` is required.
- `repos` lists dnf repositories to **enable**, by repo id. Each becomes a
  `microdnf --enablerepo=<id>` flag applied to the package installs in both the
  builder and the final stage — one list serves both, since a package that
  needs an extra repo to build usually needs it to run as well. The ids must be
  repositories the base image already **defines**; the OL9 images ship a number
  of them disabled, notably `ol9_codeready_builder`, which carries the `-devel`
  subpackages (`rrdtool-devel`, and every other `-devel` on RHEL9/OL9).

  A repository the base image does not define at all cannot be reached this
  way — EPEL is the case in practice, and it needs `oracle-epel-release-el9`
  installed before its repo exists. Services needing EPEL install that package
  in their own `Ctl/docker/Dockerfile.tasks` (`ixctl` and `prefixctl` do, for
  `bgpq4`).
- Absent keys get their defaults; **present keys replace the default
  entirely** (no merging — a service that adds a runtime package must restate
  `libgcc`/`libpq` if it still needs them, as `devicectl` does for
  `rrdtool`).
- Unknown keys are a **hard error** — the build aborts.
- Package names are **OL9 microdnf** package names (the runtime base is
  `oraclelinux:9-slim-fips`), e.g. `libpq` not `postgresql-libs`,
  `gcc-c++` not `g++`.

Current non-default manifests: `auditctl`/`ixctl` add `build_deps: [rust,
cargo]`; `devicectl` enables CodeReady Builder via `repos:
[ol9_codeready_builder]` for `rrdtool-devel`, and adds `rrdtool` (from
`ol9_appstream`) and `libstdc++` to `run_deps`; `regctl` builds with `gcc-c++`, runs with only
`libgcc` (no postgres), and uses `cmd: fastapi`.

## `Dockerfile.service`

A single parameterized multi-stage build at the monorepo root replaces the
old per-service Dockerfiles. It is always built with the repo root as
context, normally via `scripts/build.py service <name>`, which derives the
build args from the manifest.

### Build arguments

| ARG | Default | Source | Description |
|---|---|---|---|
| `service_dir` | (required) | entrypoint | service dir relative to repo root (`service/<name>` or `private/<name>`) |
| `repos` | `""` | manifest `repos` | pre-rendered `--enablerepo=<id>` flags applied to the microdnf installs in both stages (space-separated) |
| `build_deps` | `""` | manifest `build_deps` | extra builder-stage microdnf packages (space-separated) |
| `run_deps` | `libgcc libpq` | manifest `run_deps` | runtime microdnf packages (space-separated) |
| `cmd` | `runserver` | manifest `cmd` | default container command (exported as `SERVICE_CMD`) |
| `builder_repo` | `fullctl/fullctl` | `--builder-repo` | builder image repository |
| `builder_tag` | `latest` | `--builder-tag` | builder image tag |
| `extra_pip_install_dir` | `""` | `--extra-pip-install-dir` | context-relative dir of plugin sdists |
| `base_repo` | `oraclelinux` | — | runtime base image repository |
| `base_tag` | `9-slim-fips` | — | runtime base image tag |
| `uid` | `6300` | — | non-root runtime uid |
| `user` | `fullctl` | — | runtime user name |
| `python_ver` | `3.11` | — | runtime python version (microdnf package) |
| `install_to` | `/srv/service` | — | service home in the image |
| `virtual_env` | `/venv` | — | venv path (built in builder, copied to runtime) |
| `run_dirs` | `locale media static` | — | writable dirs chowned to `uid` |

### How it works

- **Builder stage** runs FROM the builder image with
  `UV_PROJECT_ENVIRONMENT=/venv`. It copies the root workspace files
  (`pyproject.toml`, `uv.lock`, `src/`) and the service's `pyproject.toml`,
  then runs `uv sync --frozen --no-install-project --no-editable` in the
  service directory. `--frozen` uses the lock as-is (lock freshness is fci0's
  `lock_and_bump` responsibility); `--no-install-project` skips installing
  the service itself — its code is COPY'd into the image instead. The `tasks`
  dependency group is never installed here.
- **Plugins**: when `extra_pip_install_dir` is set, its sdists are COPY'd
  (the service's `.gitignore` acts as a placeholder so the COPY works when
  the arg is empty) and installed with `uv pip install ./plugins/*.tar.gz`
  (uv venvs ship without pip).
- **Runtime stage** is FROM `oraclelinux:9-slim-fips`: python and `run_deps`
  installed via microdnf, non-root `uid` 6300, the venv copied from the
  builder, and the service source COPY'd to `main/` (not pip-installed).
  Optional per-service files (`docs/`, `fixtures/`, `django-uwsgi.ini`,
  `manage.sh`) are staged when present.
- **CMD shim**: exec-form CMD cannot expand build args, so the manifest's
  `cmd` is carried in the `SERVICE_CMD` env var. The `/entrypoint` shim runs
  `entrypoint.sh $SERVICE_CMD` when the container is started with no
  arguments; explicit arguments pass through to `entrypoint.sh` unchanged and
  can also be overridden at runtime via `SERVICE_CMD`.

## Builder Image (root `Dockerfile`)

`scripts/build.py builder` builds the shared builder image
(`fullctl/fullctl`) from the root `Dockerfile`: `oraclelinux:9-slim-fips`
with `python3.11` + `python3.11-devel` and the C build toolchain installed
via microdnf (slim OL9 ships no Python; uwsgi builds from sdist and needs the
interpreter headers), uv copied in from `ghcr.io/astral-sh/uv`, and the core
library venv pre-built from the root lock so per-service syncs in
`Dockerfile.service` are incremental on top of it.

**FIPS note**: the base image runs in FIPS mode; `md5` usages in application
code need `usedforsecurity=False` (supported by OL9 python3.11). This is
flagged for real-build validation rather than patched blind.

## Workspace and Lock Model

- The monorepo root `pyproject.toml` declares a **uv workspace** with
  `members = ["service/*"]` — the core `fullctl` library plus the nine public
  services.
- There is **one `uv.lock` at the monorepo root** covering all workspace
  members. Services depend on core via `fullctl` +
  `[tool.uv.sources] fullctl = { workspace = true }`. There are no
  per-service locks for public services and no `poetry.lock` files.
- **Private overlay services** (`private/<name>/`, cloned in from
  fullctl-private at build time) are deliberately *not* workspace members —
  the root lock must not change depending on whether `private/` is present.
  They are standalone projects that reference core via
  `[tool.uv.sources] fullctl = { path = "../.." }`, which only resolves in
  the assembled tree, and each carries its **own `uv.lock` generated in the
  assembled tree** (a standalone fullctl-private checkout cannot resolve the
  path dependency). `Dockerfile.service` copies `<service_dir>/uv.lock*` — the
  glob matches the private lock when building an overlay service and matches
  nothing for public members, which resolve against the root lock.
- **Private locks can go stale against the core**: they freeze a snapshot of
  the core dependency set, and `uv sync --frozen` does **not** revalidate a
  path dependency's metadata — a dep added to the root `pyproject.toml` would
  be silently missing from the private images. Regeneration is fci0's job:
  `lock_and_bump` runs `uv lock` per private service in the assembled tree
  (triggered by a changed monorepo checkout or `--lock`), and `fci0 build`
  refuses to build against a stale lock (`uv lock --check`) otherwise. When
  regenerating by hand: assemble the tree (clone fullctl-private into
  `private/`), then `uv lock` inside `private/<name>/`.
- Optional dependency sets use PEP 735 `[dependency-groups]`; the
  `tasks` group (ixctl, prefixctl) is excluded from service image syncs and
  installed only in tasks image builds via `uv sync --group tasks`.

### uv-only installability

The pyprojects are PEP 621 with `[tool.uv.sources]` for the core dependency.
`tool.uv.sources` is uv-specific: **Poetry (or plain pip from source) can no
longer install these projects**. All dependency management — locking,
syncing, building sdists/wheels — goes through uv.

## Tasks Images

A service that ships a `Ctl/docker/Dockerfile.tasks` gets a second image per
build — the trigger is purely the **existence of that file** (currently ixctl
and prefixctl). `scripts/build.py service <name>` builds it automatically
after the service image, with the same tag and the repository suffix
`-tasks` (after any `--image-suffix`): `fullctl/<name><sfx>-tasks`. Pass
`--no-tasks` to skip it.

Unlike the service image, the tasks build does **not** receive the
manifest-derived `build_deps`/`run_deps`/`cmd`/`repos` build args — the manifest
describes the service image only, and one dep set cannot serve both (e.g.
prefixctl's service image must not ship `bgpq4` while its tasks image needs
it). The tasks Dockerfiles declare their own dep defaults; only
`service_dir` and `extra_pip_install_dir` are forwarded.

The tasks Dockerfiles are uv builds on `oraclelinux:9-slim-fips` (matching
`Dockerfile.service`) that sync the service's locked dependency set **plus
the `tasks` dependency group and without the `dev` group** (`uv sync
--frozen --no-install-project --no-editable --no-default-groups --group
tasks` — uv installs `dev` by default; the old poetry tasks images were
built `--only main,tasks`) and add task-specific tooling (e.g. `bgpq4` from
EPEL). Note the service images are different: they keep the default `dev`
group, matching the old `poetry install --no-root`, and the entrypoint's
`run_tests` mode needs pytest.

## Building Locally

You need docker and [uv](https://docs.astral.sh/uv/). From the monorepo root
(the first invocation fetches PyYAML per the script's inline metadata):

```sh
# build the builder image first (service builds consume it)
uv run scripts/build.py builder --registry localhost:5000 --tag dev

# build a service against that builder -- --builder-repo must carry the
# registry, otherwise the FROM resolves to fullctl/fullctl on Docker Hub
uv run scripts/build.py service ixctl --registry localhost:5000 --tag dev \
    --builder-repo localhost:5000/fullctl/fullctl --builder-tag dev

# skip the tasks image while iterating
uv run scripts/build.py service ixctl --registry localhost:5000 --tag dev \
    --builder-repo localhost:5000/fullctl/fullctl --builder-tag dev --no-tasks

# plugin-augmented base with a decorated repository name
uv run scripts/build.py service peerctl --registry localhost:5000 --tag dev \
    --builder-repo localhost:5000/fullctl/fullctl --builder-tag dev \
    --image-suffix -fl --extra-pip-install-dir plugins-dist

# push after building (the builder must already exist in that registry:
# `builder --registry reg.example.com --tag 1.2.3 --push`)
uv run scripts/build.py service aaactl --registry reg.example.com --tag 1.2.3 \
    --builder-repo reg.example.com/fullctl/fullctl --builder-tag 1.2.3 --push
```

The built refs are on the last stdout line:

```sh
uv run scripts/build.py service ixctl --registry localhost:5000 --tag dev \
    --builder-repo localhost:5000/fullctl/fullctl --builder-tag dev \
    | tail -n 1 | python3 -m json.tool
```

## Related Documentation

- [Monorepo layout, private overlay, service lookup order](monorepo.md)
- [uv Workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)

## Legacy nested overlays (fullctl-private)

`fullctl-private/fullctl/{aaactl,devicectl,ixctl,peerctl,prefixctl}` are
split-repo-era overlay remnants. They are not resolvable by the
`private/<name>` service lookup, are not built by `scripts/build.py`, and are
deliberately excluded from the poetry→uv conversion (decision 2026-07-12).
They keep their legacy files until cleaned up separately.
