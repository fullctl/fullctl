# FullCtl Monorepo

The FullCtl monorepo consolidates all FullCtl services into a single repository with a shared codebase and dependency management.

## Directory Structure

```
fullctl/
├── pyproject.toml          # Workspace root, fullctl library
├── uv.lock                  # Single lockfile for all services
├── src/fullctl/             # Shared fullctl library code
├── Ctl/
│   └── container/           # Unified Containerfiles
│       ├── Containerfile.service
│       └── Containerfile.tasks
├── service/                 # Public services
│   ├── aaactl/
│   ├── aclctl/
│   ├── auditctl/
│   ├── devicectl/
│   ├── ixctl/
│   ├── pdbctl/
│   ├── peerctl/
│   ├── prefixctl/
│   └── regctl/
└── private/                 # Private overlay (cloned at build time)
    └── <service>/           # Private service overrides
```

### Service Directory Structure

Each service follows this structure:

```
service/<name>/
├── Ctl/
│   ├── VERSION             # Service version (required)
│   └── docker/
│       ├── entrypoint.sh
│       ├── django-uwsgi.ini
│       └── manage.sh
├── pyproject.toml          # Service dependencies
├── src/<name>/             # Python package
└── docs/                   # Service documentation
```

## Service Lookup Order

When building a service, fci0 looks for the service path in this order:

1. **Explicit subdir** - `subdir` key in fci.yaml source config
2. **Single repo** (legacy) - Service name matches repo name, `Ctl/VERSION` at root
3. **Private overlay** - `{repo}/private/{service}/Ctl/VERSION`
4. **Public service** - `{repo}/service/{service}/Ctl/VERSION`

The first match wins. This means private services take precedence over public ones.

## Private Overlay

The private overlay allows proprietary or customer-specific code to be layered on top of the public monorepo.

### How It Works

1. A separate private repo (e.g., `fullctl-private`) mirrors the `service/` structure
2. During build, fci0 clones the private repo INTO `monorepo/private/`
3. Services in `private/` override those in `service/`

### Private Repo Structure

```
fullctl-private/
└── <service>/
    ├── Ctl/
    │   └── VERSION
    ├── pyproject.toml
    └── src/<service>/
```

### Use Cases

- Proprietary features not in the open source release
- Customer-specific whitelabel builds
- Internal tooling or integrations

## Development Workflow

### Adding a New Public Service

1. Create the service directory:
   ```bash
   mkdir -p service/<name>/Ctl/docker service/<name>/src/<name>
   ```

2. Create `Ctl/VERSION`:
   ```bash
   echo "0.1.0" > service/<name>/Ctl/VERSION
   ```

3. Create `pyproject.toml`:
   ```toml
   [project]
   name = "<name>"
   version = "0.1.0"
   description = "Description"
   requires-python = ">=3.9"
   dependencies = [
       "fullctl",
   ]

   [tool.uv.sources]
   fullctl = { workspace = true }

   [tool.fci0]
   run_deps = ["postgresql-libs"]

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [tool.hatch.build.targets.wheel]
   packages = ["src/<name>"]
   ```

4. Update the workspace lockfile:
   ```bash
   uv lock
   ```

### Adding a New Private Service

1. In the private repo, create `<service>/` with the same structure as above

2. Configure fci.yaml to use the private repo:
   ```yaml
   fci:
     deploy_private: https://gitlab.fullctl.com/fullctl/fullctl-private
     deploy_private_branch: main
   ```

3. The private service will automatically override the public version during build

### Working with Dependencies

All services share a single `uv.lock` at the monorepo root:

```bash
# Add a dependency to a service
cd service/<name>
# Edit pyproject.toml to add dependency
cd ../..
uv lock  # Update workspace lockfile
```

## fci0 Configuration

### fci.yaml Reference

```yaml
fci:
  # Public monorepo settings
  deploy_monorepo: https://gitlab.fullctl.com/fullctl/fullctl
  deploy_branch: monorepo

  # Private overlay (optional)
  deploy_private: https://gitlab.fullctl.com/fullctl/fullctl-private
  deploy_private_branch: main

  # Container registry
  cluster_registry: r.gitlab.fullctl.com/fci/registry

  # Kubernetes context
  kubie_ctx: 20c-lonepine

  # Overlay version tag
  overlay_vtag: fl

  # Services to build/deploy
  services:
  - aaactl
  - aclctl
  - devicectl
  # ...

# Per-service source overrides
sources:
  <service>:
    # Override repo/branch for this service
    repo_url: https://gitlab.fullctl.com/fullctl/fullctl
    branch: monorepo
    private_branch: main  # Branch for private overlay

    # Explicit subdir (optional)
    subdir: service/<name>

    # External plugins
    plugins:
    - repo: git@gitlab.fullctl.com:fullctl/prefixctl-reputation
      version: main

# Version state tracking
state:
  <service>:
    version: 1.0.0-rc.1
    build_index: 0
```

### Service pyproject.toml [tool.fci0]

Docker build configuration is stored in each service's `pyproject.toml`:

```toml
[tool.fci0]
# Runtime dependencies (dnf packages)
run_deps = ["postgresql-libs", "rrdtool"]

# Build-time dependencies
build_deps = ["rrdtool-devel"]

# uv sync groups (e.g., "--no-group tasks")
uv_groups = ""

# Default entrypoint command
default_cmd = "runserver"  # or "fastapi" for regctl
```

## Building with fci0

```bash
# Build a single service
fci0 build <config_dir> <service>

# Build with dependency lock and version bump
fci0 build <config_dir> <service> --lock

# Build all services
fci0 build <config_dir>

# Deploy a service
fci0 deploy <config_dir> <service>
```

## Related Documentation

- [fctlops CLAUDE.md](https://gitlab.fullctl.com/fullctl/fctlops) - fci0 CLI reference
- [uv Workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) - Dependency management
