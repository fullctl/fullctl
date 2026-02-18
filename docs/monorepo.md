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

When building, services are located in this priority order:

1. **Explicit subdir** - configured in build tool
2. **Single repo** (legacy) - service name matches repo name, `Ctl/VERSION` at root
3. **Private overlay** - `private/{service}/Ctl/VERSION`
4. **Public service** - `service/{service}/Ctl/VERSION`

The first match wins. Private services take precedence over public ones.

## Private Overlay

The private overlay allows proprietary or customer-specific code to be layered on top of the public monorepo.

### How It Works

1. A separate private repo (e.g., `fullctl-private`) mirrors the `service/` structure
2. During build, the private repo is cloned INTO `monorepo/private/`
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
2. Configure the build tool to use the private repo
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

## Related Documentation

- [uv Workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) - Dependency management
