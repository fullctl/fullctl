#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""Build FullCtl monorepo docker images.

This is the ONLY interface used to build monorepo images (fci0 delegates here):

    uv run scripts/build.py builder --registry REG --tag TAG [--push]
    uv run scripts/build.py service NAME --registry REG --tag TAG
        [--push] [--builder-repo R --builder-tag T]
        [--image-suffix SFX] [--extra-pip-install-dir RELPATH] [--no-tasks]

- ``builder`` builds the root builder image (root ``Dockerfile``); its
  repository name is pinned ``fullctl/fullctl``.
- ``service`` resolves the service path (``private/<name>/`` first, then
  ``service/<name>/``), loads ``<service_path>/Ctl/docker.yaml`` and runs
  ``docker build`` with the repo root as context, ``-f Dockerfile.service``
  and the manifest-derived ``--build-arg``s. If
  ``<service_path>/Ctl/docker/Dockerfile.tasks`` exists, the tasks image
  (repository suffix ``-tasks``, same tag) is also built unless ``--no-tasks``.

Docker output interleaves on stdout; the built image refs are printed as JSON
on the LAST stdout line, e.g.

    {"service": "reg/fullctl/ixctl:1.2.3", "tasks": "reg/fullctl/ixctl-tasks:1.2.3"}

(``builder`` prints ``{"builder": "reg/fullctl/fullctl:1.2.3"}``.)
Consumers must parse the last stdout line only.

Full contract: docs/build.md
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

DOCS = "docs/build.md"

MANIFEST_DEFAULTS = {
    "build_deps": [],
    "run_deps": ["libgcc", "libpq"],
    "cmd": "runserver",
    "repos": [],
}
MANIFEST_KEYS = {"schema"} | set(MANIFEST_DEFAULTS)


class BuildError(Exception):
    """Fatal build error; message already names the offending file."""


def fail(msg):
    raise BuildError(f"{msg} (see {DOCS})")


def load_manifest(path):
    """Load and validate a schema-1 Ctl/docker.yaml manifest.

    Returns {"build_deps": [...], "run_deps": [...], "cmd": str, "repos": [...]}
    with defaults applied for absent keys; present keys replace defaults
    entirely.
    """
    if not path.is_file():
        fail(f"missing manifest {path}")

    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        fail(f"malformed YAML in {path}: {exc}")

    if not isinstance(data, dict) or not isinstance(data.get("docker"), dict):
        fail(f"{path} must contain a 'docker' mapping")

    docker = data["docker"]

    unknown = set(docker) - MANIFEST_KEYS
    if unknown:
        fail(f"unknown key(s) {sorted(unknown)} in {path}")

    if docker.get("schema") != 1:
        fail(f"{path} must declare 'schema: 1', got {docker.get('schema')!r}")

    manifest = {}
    for key, default in MANIFEST_DEFAULTS.items():
        value = docker.get(key, default)
        if isinstance(default, list):
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                fail(f"'{key}' in {path} must be a list of strings, got {value!r}")
        elif not isinstance(value, str):
            fail(f"'{key}' in {path} must be a string, got {value!r}")
        manifest[key] = value

    return manifest


def resolve_service_path(root, name):
    """Resolve a service dir in fci0's order: private/<name>/, then service/<name>/."""
    if name == "fullctl":
        fail("'service fullctl' is not buildable; use the 'builder' subcommand")

    for prefix in ("private", "service"):
        path = root / prefix / name
        if path.is_dir():
            return path

    fail(f"service '{name}' not found under {root / 'private'} or {root / 'service'}")


def image_ref(registry, repository, tag):
    return f"{registry.rstrip('/')}/{repository}:{tag}"


def run_docker(cmd):
    """Run a docker command, streaming its output; fail fast on non-zero exit."""
    print(f"+ {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        fail(f"command failed with exit code {proc.returncode}: {' '.join(cmd)}")


def docker_build(root, dockerfile, ref, build_args):
    if not dockerfile.is_file():
        fail(f"missing {dockerfile}")

    cmd = ["docker", "build", str(root), "-f", str(dockerfile)]
    for name, value in build_args:
        cmd += ["--build-arg", f"{name}={value}"]
    cmd += ["-t", ref]
    run_docker(cmd)


def cmd_builder(args, root):
    ref = image_ref(args.registry, "fullctl/fullctl", args.tag)
    docker_build(root, root / "Dockerfile", ref, [])
    if args.push:
        run_docker(["docker", "push", ref])
    return {"builder": ref}


def cmd_service(args, root):
    service_path = resolve_service_path(root, args.name)
    manifest = load_manifest(service_path / "Ctl" / "docker.yaml")

    if not args.builder_repo:
        print(
            "warning: --builder-repo not given; Dockerfile.service falls back to"
            " fullctl/fullctl:latest on Docker Hub, which is probably not the"
            " builder you just built",
            file=sys.stderr,
        )

    build_args = [
        ("service_dir", service_path.relative_to(root).as_posix()),
        ("build_deps", " ".join(manifest["build_deps"])),
        ("run_deps", " ".join(manifest["run_deps"])),
        ("cmd", manifest["cmd"]),
        # rendered as microdnf flags rather than a bare list: manifest repos
        # name repositories the base image defines but ships disabled
        ("repos", " ".join(f"--enablerepo={r}" for r in manifest["repos"])),
    ]
    if args.builder_repo:
        build_args.append(("builder_repo", args.builder_repo))
    if args.builder_tag:
        build_args.append(("builder_tag", args.builder_tag))
    if args.extra_pip_install_dir:
        build_args.append(("extra_pip_install_dir", args.extra_pip_install_dir))

    repository = f"fullctl/{args.name}{args.image_suffix}"
    ref = image_ref(args.registry, repository, args.tag)
    docker_build(root, root / "Dockerfile.service", ref, build_args)

    refs = {"service": ref}

    tasks_dockerfile = service_path / "Ctl" / "docker" / "Dockerfile.tasks"
    if tasks_dockerfile.is_file() and not args.no_tasks:
        # the tasks Dockerfiles own their build_deps/run_deps ARG defaults --
        # forwarding the service manifest's values would override them (one
        # manifest cannot serve both images, e.g. prefixctl's service image
        # must not get bgpq4 while its tasks image needs it). Only the path
        # args are forwarded.
        tasks_build_args = [
            ("service_dir", service_path.relative_to(root).as_posix()),
        ]
        if args.extra_pip_install_dir:
            tasks_build_args.append(
                ("extra_pip_install_dir", args.extra_pip_install_dir)
            )
        tasks_ref = image_ref(args.registry, f"{repository}-tasks", args.tag)
        docker_build(root, tasks_dockerfile, tasks_ref, tasks_build_args)
        refs["tasks"] = tasks_ref

    if args.push:
        for pushed in refs.values():
            run_docker(["docker", "push", pushed])

    return refs


def make_parser():
    parser = argparse.ArgumentParser(
        prog="build.py",
        description=f"Build FullCtl monorepo docker images (contract: {DOCS}).",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    builder = sub.add_parser("builder", help="build the root builder image")
    builder.add_argument("--registry", required=True, help="image registry")
    builder.add_argument("--tag", required=True, help="image tag")
    builder.add_argument("--push", action="store_true", help="push after build")
    builder.set_defaults(func=cmd_builder)

    service = sub.add_parser("service", help="build a service image")
    service.add_argument("name", help="service name")
    service.add_argument("--registry", required=True, help="image registry")
    service.add_argument("--tag", required=True, help="image tag")
    service.add_argument("--push", action="store_true", help="push after build")
    service.add_argument("--builder-repo", help="builder image repository")
    service.add_argument("--builder-tag", help="builder image tag")
    service.add_argument(
        "--image-suffix",
        default="",
        help="suffix appended to the repository name: fullctl/<name><sfx>",
    )
    service.add_argument(
        "--extra-pip-install-dir",
        help="repo-relative dir of extra packages to pip install (plugins)",
    )
    service.add_argument(
        "--no-tasks", action="store_true", help="skip the tasks image build"
    )
    service.set_defaults(func=cmd_service)

    return parser


def normalize_argv(argv):
    """Join --image-suffix with its value (suffixes like '-fl' start with '-',
    which argparse would otherwise mistake for an option)."""
    out = []
    it = iter(argv)
    for token in it:
        if token == "--image-suffix":
            value = next(it, None)
            # test on '--', not '-': legitimate suffixes are '-fl', '-20c' &c,
            # so only a double-dash token is unambiguously the next option
            if value is None or value.startswith("--"):
                fail("--image-suffix requires a value")
            out.append(f"--image-suffix={value}")
        else:
            out.append(token)
    return out


def main(argv=None, repo_root=None):
    if argv is None:
        argv = sys.argv[1:]
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[1]

    try:
        args = make_parser().parse_args(normalize_argv(argv))
        refs = args.func(args, root)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # image refs as JSON on the LAST stdout line; docker noise interleaves above
    print(json.dumps(refs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
