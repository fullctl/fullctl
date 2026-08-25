"""Tests for scripts/build.py — subprocess is mocked, docker never runs.

Run with: uv run --with pytest --with pyyaml pytest scripts/test_build.py -q
"""

import json
import subprocess

import build
import pytest

REGISTRY = "reg.example.com"
TAG = "1.2.3"


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def root(tmp_path):
    """A minimal monorepo root with both root dockerfiles."""
    (tmp_path / "Dockerfile").write_text("# builder dockerfile\n")
    (tmp_path / "Dockerfile.service").write_text("# service dockerfile\n")
    return tmp_path


def add_service(
    root, name, manifest="docker:\n  schema: 1\n", prefix="service", tasks=False
):
    ctl = root / prefix / name / "Ctl"
    ctl.mkdir(parents=True)
    if manifest is not None:
        (ctl / "docker.yaml").write_text(manifest)
    if tasks:
        (ctl / "docker").mkdir()
        (ctl / "docker" / "Dockerfile.tasks").write_text("# tasks dockerfile\n")
    return root / prefix / name


class DockerRecorder(list):
    """Records docker invocations; commands matching a fail_on substring fail."""

    def __init__(self):
        super().__init__()
        self.fail_on = []


@pytest.fixture
def docker(monkeypatch):
    """Record docker invocations; emit fake docker noise on stdout."""
    calls = DockerRecorder()

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        print(f"#{len(calls)} ---> some docker noise for {cmd[1]}")
        print("Step 1/9 : FROM something")
        rc = 1 if any(s in " ".join(cmd) for s in calls.fail_on) else 0
        return subprocess.CompletedProcess(cmd, rc)

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    return calls


def run_main(argv, root):
    return build.main(argv, repo_root=root)


def last_stdout_json(capsys):
    out = capsys.readouterr().out
    return json.loads(out.strip().splitlines()[-1]), out


def build_args_of(cmd):
    """Extract --build-arg name=value pairs from a docker command as a dict."""
    args = {}
    for i, tok in enumerate(cmd):
        if tok == "--build-arg":
            name, _, value = cmd[i + 1].partition("=")
            args[name] = value
    return args


SERVICE_ARGS = ["--registry", REGISTRY, "--tag", TAG]


# --- manifest loading -------------------------------------------------------


def test_manifest_defaults(root):
    path = add_service(root, "aaactl") / "Ctl" / "docker.yaml"
    manifest = build.load_manifest(path)
    assert manifest == {
        "build_deps": [],
        "run_deps": ["libgcc", "libpq"],
        "cmd": "runserver",
        "repos": [],
    }


def test_manifest_present_key_replaces_default(root):
    path = (
        add_service(
            root,
            "regctl",
            manifest=(
                "docker:\n"
                "  schema: 1\n"
                "  build_deps: [g++]\n"
                "  run_deps: [libgcc]\n"
                "  cmd: fastapi\n"
            ),
        )
        / "Ctl"
        / "docker.yaml"
    )
    manifest = build.load_manifest(path)
    # present keys REPLACE defaults entirely (no merge)
    assert manifest == {
        "build_deps": ["g++"],
        "run_deps": ["libgcc"],
        "cmd": "fastapi",
        "repos": [],
    }


def test_manifest_partial_override_keeps_other_defaults(root):
    path = (
        add_service(
            root,
            "devicectl",
            manifest="docker:\n  schema: 1\n  run_deps: [libgcc, libpq, rrdtool]\n",
        )
        / "Ctl"
        / "docker.yaml"
    )
    manifest = build.load_manifest(path)
    assert manifest["run_deps"] == ["libgcc", "libpq", "rrdtool"]
    assert manifest["build_deps"] == []
    assert manifest["cmd"] == "runserver"


def test_manifest_repos_defaults_empty(root):
    path = add_service(root, "aaactl") / "Ctl" / "docker.yaml"
    assert build.load_manifest(path)["repos"] == []


def test_manifest_repos_parsed(root):
    path = (
        add_service(
            root,
            "devicectl",
            manifest=(
                "docker:\n"
                "  schema: 1\n"
                "  repos: [ol9_codeready_builder]\n"
                "  build_deps: [rrdtool-devel]\n"
            ),
        )
        / "Ctl"
        / "docker.yaml"
    )
    manifest = build.load_manifest(path)
    assert manifest["repos"] == ["ol9_codeready_builder"]
    assert manifest["build_deps"] == ["rrdtool-devel"]
    assert manifest["run_deps"] == ["libgcc", "libpq"]


def test_repos_forwarded_as_enablerepo_flags(root, docker):
    add_service(
        root,
        "devicectl",
        manifest="docker:\n  schema: 1\n  repos: [ol9_codeready_builder]\n",
    )
    assert run_main(["service", "devicectl", *SERVICE_ARGS], root) == 0
    assert build_args_of(docker[0])["repos"] == "--enablerepo=ol9_codeready_builder"


def test_multiple_repos_each_get_a_flag(root, docker):
    add_service(
        root,
        "devicectl",
        manifest="docker:\n  schema: 1\n  repos: [ol9_codeready_builder, ol9_addons]\n",
    )
    assert run_main(["service", "devicectl", *SERVICE_ARGS], root) == 0
    assert (
        build_args_of(docker[0])["repos"]
        == "--enablerepo=ol9_codeready_builder --enablerepo=ol9_addons"
    )


def test_repos_build_arg_empty_when_absent(root, docker):
    add_service(root, "aaactl")
    assert run_main(["service", "aaactl", *SERVICE_ARGS], root) == 0
    assert build_args_of(docker[0])["repos"] == ""


@pytest.mark.parametrize(
    "manifest,fragment",
    [
        ("docker:\n  schema: 1\n  bogus: 1\n", "unknown key"),  # unknown key
        ("docker:\n  schema: 2\n", "schema"),  # wrong schema
        ("docker:\n  build_deps: []\n", "schema"),  # missing schema
        ("docker: [1, 2]\n", "docker"),  # docker not a mapping
        ("something_else: 1\n", "docker"),  # no docker key
        ("docker: {schema: 1, build_deps: rust}\n", "build_deps"),  # not a list
        ("docker: {schema: 1, run_deps: [libgcc, 1]}\n", "run_deps"),  # non-str item
        ("docker: {schema: 1, cmd: [runserver]}\n", "cmd"),  # cmd not a string
        ("docker: [unbalanced\n", "malformed"),  # yaml parse error
    ],
)
def test_manifest_invalid(root, manifest, fragment):
    path = add_service(root, "aaactl", manifest=manifest) / "Ctl" / "docker.yaml"
    with pytest.raises(build.BuildError) as exc:
        build.load_manifest(path)
    message = str(exc.value)
    assert fragment in message
    assert str(path) in message  # names the offending file
    assert "docs/build.md" in message  # points at the contract


def test_manifest_missing_file(root):
    add_service(root, "aaactl", manifest=None)
    path = root / "service" / "aaactl" / "Ctl" / "docker.yaml"
    with pytest.raises(build.BuildError) as exc:
        build.load_manifest(path)
    assert str(path) in str(exc.value)
    assert "docs/build.md" in str(exc.value)


def test_manifest_error_exits_nonzero_via_cli(root, docker, capsys):
    add_service(root, "aaactl", manifest="docker:\n  schema: 1\n  bogus: 1\n")
    rc = run_main(["service", "aaactl", *SERVICE_ARGS], root)
    assert rc != 0
    err = capsys.readouterr().err
    assert "bogus" in err
    assert "docs/build.md" in err
    assert docker == []  # nothing was built


# --- service path resolution ------------------------------------------------


def test_private_resolved_before_service(root, docker):
    add_service(root, "aclctl", prefix="service")
    add_service(root, "aclctl", prefix="private")
    rc = run_main(["service", "aclctl", *SERVICE_ARGS], root)
    assert rc == 0
    assert build_args_of(docker[0])["service_dir"] == "private/aclctl"


def test_public_service_resolved(root, docker):
    add_service(root, "ixctl")
    rc = run_main(["service", "ixctl", *SERVICE_ARGS], root)
    assert rc == 0
    assert build_args_of(docker[0])["service_dir"] == "service/ixctl"


def test_unknown_service_rejected(root, docker, capsys):
    rc = run_main(["service", "nosuch", *SERVICE_ARGS], root)
    assert rc != 0
    err = capsys.readouterr().err
    assert "nosuch" in err
    assert "docs/build.md" in err
    assert docker == []


def test_service_fullctl_rejected(root, docker, capsys):
    # even if a directory exists, `service fullctl` must be rejected
    add_service(root, "fullctl", prefix="private")
    rc = run_main(["service", "fullctl", *SERVICE_ARGS], root)
    assert rc != 0
    assert "builder" in capsys.readouterr().err
    assert docker == []


# --- docker command assembly ------------------------------------------------


def test_service_build_command(root, docker):
    add_service(
        root,
        "ixctl",
        manifest="docker:\n  schema: 1\n  build_deps: [rust, cargo]\n",
    )
    rc = run_main(["service", "ixctl", *SERVICE_ARGS], root)
    assert rc == 0
    assert len(docker) == 1
    cmd = docker[0]
    assert cmd[:3] == ["docker", "build", str(root)]  # repo-root context
    fidx = cmd.index("-f")
    assert cmd[fidx + 1] == str(root / "Dockerfile.service")
    tidx = cmd.index("-t")
    assert cmd[tidx + 1] == f"{REGISTRY}/fullctl/ixctl:{TAG}"
    assert build_args_of(cmd) == {
        "service_dir": "service/ixctl",
        "build_deps": "rust cargo",  # space-joined
        "run_deps": "libgcc libpq",
        "cmd": "runserver",
        "repos": "",
    }


def test_builder_repo_and_tag_forwarded(root, docker):
    add_service(root, "peerctl")
    rc = run_main(
        [
            "service",
            "peerctl",
            *SERVICE_ARGS,
            "--builder-repo",
            "reg/fullctl/fullctl",
            "--builder-tag",
            "0.1.0",
        ],
        root,
    )
    assert rc == 0
    args = build_args_of(docker[0])
    assert args["builder_repo"] == "reg/fullctl/fullctl"
    assert args["builder_tag"] == "0.1.0"


def test_warns_when_builder_repo_omitted(root, docker, capsys):
    add_service(root, "peerctl")
    assert run_main(["service", "peerctl", *SERVICE_ARGS], root) == 0
    assert "--builder-repo" in capsys.readouterr().err


def test_no_warning_when_builder_repo_given(root, docker, capsys):
    add_service(root, "peerctl")
    assert (
        run_main(
            [
                "service",
                "peerctl",
                *SERVICE_ARGS,
                "--builder-repo",
                "reg/fullctl/fullctl",
            ],
            root,
        )
        == 0
    )
    assert "--builder-repo" not in capsys.readouterr().err


def test_optional_build_args_absent_when_not_given(root, docker):
    add_service(root, "peerctl")
    run_main(["service", "peerctl", *SERVICE_ARGS], root)
    args = build_args_of(docker[0])
    assert "builder_repo" not in args
    assert "builder_tag" not in args
    assert "extra_pip_install_dir" not in args


def test_extra_pip_install_dir_forwarded(root, docker):
    add_service(root, "peerctl")
    run_main(
        [
            "service",
            "peerctl",
            *SERVICE_ARGS,
            "--extra-pip-install-dir",
            "service/peerctl/plugins",
        ],
        root,
    )
    assert build_args_of(docker[0])["extra_pip_install_dir"] == (
        "service/peerctl/plugins"
    )


def test_push_flag(root, docker):
    add_service(root, "pdbctl")
    rc = run_main(["service", "pdbctl", *SERVICE_ARGS, "--push"], root)
    assert rc == 0
    assert docker[-1] == ["docker", "push", f"{REGISTRY}/fullctl/pdbctl:{TAG}"]


def test_no_push_by_default(root, docker):
    add_service(root, "pdbctl")
    run_main(["service", "pdbctl", *SERVICE_ARGS], root)
    assert all(cmd[1] != "push" for cmd in docker)


# --- --image-suffix ---------------------------------------------------------


@pytest.mark.parametrize(
    "suffix_args",
    [
        ["--image-suffix", "-fl"],  # separate-token form (fci0 passes -<vtag>)
        ["--image-suffix=-fl"],  # = form
    ],
)
def test_image_suffix_appended_to_repository(root, docker, capsys, suffix_args):
    add_service(root, "peerctl", tasks=True)
    rc = run_main(["service", "peerctl", *SERVICE_ARGS, *suffix_args], root)
    assert rc == 0
    refs, _ = last_stdout_json(capsys)
    assert refs["service"] == f"{REGISTRY}/fullctl/peerctl-fl:{TAG}"
    # tasks image derives from the suffixed repository, same tag
    assert refs["tasks"] == f"{REGISTRY}/fullctl/peerctl-fl-tasks:{TAG}"


@pytest.mark.parametrize(
    "argv",
    [
        ["service", "peerctl", "--image-suffix", "--push"],  # eats the next flag
        ["service", "peerctl", "--image-suffix"],  # nothing follows
    ],
)
def test_image_suffix_requires_a_value(argv):
    with pytest.raises(build.BuildError) as exc:
        build.normalize_argv(argv)
    assert "--image-suffix" in str(exc.value)


def test_image_suffix_accepts_leading_dash_value():
    assert build.normalize_argv(["--image-suffix", "-fl"]) == ["--image-suffix=-fl"]


def test_image_suffix_without_value_exits_nonzero_via_cli(root, docker, capsys):
    add_service(root, "peerctl")
    rc = run_main(
        ["service", "peerctl", *SERVICE_ARGS, "--image-suffix", "--push"], root
    )
    assert rc != 0
    assert "--image-suffix" in capsys.readouterr().err
    assert docker == []


# --- tasks image ------------------------------------------------------------


def test_tasks_image_built_when_dockerfile_exists(root, docker, capsys):
    service_path = add_service(root, "ixctl", tasks=True)
    rc = run_main(["service", "ixctl", *SERVICE_ARGS], root)
    assert rc == 0
    assert len(docker) == 2
    tasks_cmd = docker[1]
    fidx = tasks_cmd.index("-f")
    assert tasks_cmd[fidx + 1] == str(
        service_path / "Ctl" / "docker" / "Dockerfile.tasks"
    )
    tidx = tasks_cmd.index("-t")
    assert tasks_cmd[tidx + 1] == f"{REGISTRY}/fullctl/ixctl-tasks:{TAG}"
    refs, _ = last_stdout_json(capsys)
    assert refs == {
        "service": f"{REGISTRY}/fullctl/ixctl:{TAG}",
        "tasks": f"{REGISTRY}/fullctl/ixctl-tasks:{TAG}",
    }


def test_tasks_build_args_exclude_manifest_values(root, docker):
    # the tasks Dockerfiles own their build_deps/run_deps defaults; the
    # manifest values feed the service image ONLY. The tasks build receives
    # exactly the path args and nothing else.
    add_service(
        root,
        "prefixctl",
        manifest="docker:\n  schema: 1\n  run_deps: [libgcc, libpq]\n",
        tasks=True,
    )
    rc = run_main(
        [
            "service",
            "prefixctl",
            *SERVICE_ARGS,
            "--builder-repo",
            "reg/fullctl/fullctl",
            "--builder-tag",
            "0.1.0",
        ],
        root,
    )
    assert rc == 0
    assert build_args_of(docker[1]) == {"service_dir": "service/prefixctl"}


def test_tasks_build_args_forward_extra_pip_install_dir(root, docker):
    add_service(root, "prefixctl", tasks=True)
    rc = run_main(
        [
            "service",
            "prefixctl",
            *SERVICE_ARGS,
            "--extra-pip-install-dir",
            "service/prefixctl/plugins",
        ],
        root,
    )
    assert rc == 0
    assert build_args_of(docker[1]) == {
        "service_dir": "service/prefixctl",
        "extra_pip_install_dir": "service/prefixctl/plugins",
    }


def test_no_tasks_flag_skips_tasks_image(root, docker, capsys):
    add_service(root, "ixctl", tasks=True)
    rc = run_main(["service", "ixctl", *SERVICE_ARGS, "--no-tasks"], root)
    assert rc == 0
    assert len(docker) == 1
    refs, _ = last_stdout_json(capsys)
    assert refs == {"service": f"{REGISTRY}/fullctl/ixctl:{TAG}"}


def test_no_tasks_image_without_dockerfile(root, docker, capsys):
    add_service(root, "aaactl", tasks=False)
    rc = run_main(["service", "aaactl", *SERVICE_ARGS], root)
    assert rc == 0
    assert len(docker) == 1
    refs, _ = last_stdout_json(capsys)
    assert "tasks" not in refs


def test_push_pushes_tasks_image_too(root, docker):
    add_service(root, "ixctl", tasks=True)
    run_main(["service", "ixctl", *SERVICE_ARGS, "--push"], root)
    pushes = [cmd for cmd in docker if cmd[1] == "push"]
    assert pushes == [
        ["docker", "push", f"{REGISTRY}/fullctl/ixctl:{TAG}"],
        ["docker", "push", f"{REGISTRY}/fullctl/ixctl-tasks:{TAG}"],
    ]


# --- builder subcommand -----------------------------------------------------


def test_builder_command(root, docker, capsys):
    rc = run_main(["builder", *SERVICE_ARGS], root)
    assert rc == 0
    assert len(docker) == 1
    cmd = docker[0]
    assert cmd[:3] == ["docker", "build", str(root)]
    fidx = cmd.index("-f")
    assert cmd[fidx + 1] == str(root / "Dockerfile")
    tidx = cmd.index("-t")
    # repository pinned fullctl/fullctl
    assert cmd[tidx + 1] == f"{REGISTRY}/fullctl/fullctl:{TAG}"
    refs, _ = last_stdout_json(capsys)
    assert refs == {"builder": f"{REGISTRY}/fullctl/fullctl:{TAG}"}


def test_builder_push(root, docker):
    rc = run_main(["builder", *SERVICE_ARGS, "--push"], root)
    assert rc == 0
    assert docker[-1] == ["docker", "push", f"{REGISTRY}/fullctl/fullctl:{TAG}"]


# --- stdout contract --------------------------------------------------------


def test_last_stdout_line_is_json_amid_docker_noise(root, docker, capsys):
    add_service(root, "prefixctl", tasks=True)
    rc = run_main(["service", "prefixctl", *SERVICE_ARGS], root)
    assert rc == 0
    refs, out = last_stdout_json(capsys)
    lines = out.strip().splitlines()
    assert len(lines) > 1  # docker noise interleaved above
    assert "docker noise" in lines[0]
    # only the LAST line parses as the refs payload
    assert refs["service"] == f"{REGISTRY}/fullctl/prefixctl:{TAG}"
    assert refs["tasks"] == f"{REGISTRY}/fullctl/prefixctl-tasks:{TAG}"


# --- error paths ------------------------------------------------------------


def test_missing_dockerfile_service(root, docker, capsys):
    (root / "Dockerfile.service").unlink()
    add_service(root, "aaactl")
    rc = run_main(["service", "aaactl", *SERVICE_ARGS], root)
    assert rc != 0
    err = capsys.readouterr().err
    assert str(root / "Dockerfile.service") in err
    assert "docs/build.md" in err
    assert docker == []


def test_missing_root_dockerfile_for_builder(root, docker, capsys):
    (root / "Dockerfile").unlink()
    rc = run_main(["builder", *SERVICE_ARGS], root)
    assert rc != 0
    assert str(root / "Dockerfile") in capsys.readouterr().err
    assert docker == []


def test_docker_build_failure_exits_nonzero(root, docker, capsys):
    add_service(root, "aaactl")
    docker.fail_on.append("docker build")
    rc = run_main(["service", "aaactl", *SERVICE_ARGS], root)
    assert rc != 0
    captured = capsys.readouterr()
    assert "exit code 1" in captured.err
    assert "docs/build.md" in captured.err
    # no JSON refs line on failure
    assert not captured.out or "{" not in captured.out.strip().splitlines()[-1]


def test_docker_push_failure_exits_nonzero(root, docker, capsys):
    add_service(root, "aaactl")
    docker.fail_on.append("docker push")
    rc = run_main(["service", "aaactl", *SERVICE_ARGS, "--push"], root)
    assert rc != 0
    assert "exit code 1" in capsys.readouterr().err


def test_tasks_build_failure_aborts(root, docker, capsys):
    add_service(root, "ixctl", tasks=True)
    docker.fail_on.append("ixctl-tasks")
    rc = run_main(["service", "ixctl", *SERVICE_ARGS], root)
    assert rc != 0
    assert "docs/build.md" in capsys.readouterr().err
