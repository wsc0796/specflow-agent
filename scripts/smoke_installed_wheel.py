"""Installed-wheel smoke: build, install into a clean venv, boot the API, run a mock workflow.

Usage:
    python scripts/smoke_installed_wheel.py
    python scripts/smoke_installed_wheel.py --wheel dist/specflow_agent-1.1.1-py3-none-any.whl
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 90
SMOKE_CREDENTIAL = secrets.token_urlsafe(32)
PROMPT_NAMES = ("analyze_requirement", "generate_spec", "review_generation")
LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

TERMINAL_STATES = frozenset(
    {
        "completed",
        "completed_degraded",
        "rejected",
        "failed_runtime",
        "failed_security",
        "budget_exceeded",
        "cancelled",
    }
)


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        details = f"stdout: {result.stdout}\nstderr: {result.stderr}"
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{details}")
    return result.stdout


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _runtime_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"} and not key.startswith("SPECFLOW_")
    }


def _server_environment(allowed_repository_root: Path) -> dict[str, str]:
    """Build a fail-closed API environment scoped to the smoke fixture."""
    environment = _runtime_environment()
    environment["SPECFLOW_API_KEY"] = SMOKE_CREDENTIAL
    environment["SPECFLOW_ALLOWED_REPOSITORY_ROOTS"] = str(allowed_repository_root)
    return environment


def _http(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    request.add_header("X-API-Key", SMOKE_CREDENTIAL)
    try:
        # The smoke server is always loopback-only. Ambient corporate/developer
        # proxies must not turn a local readiness probe into an external request.
        with LOOPBACK_OPENER.open(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code} on {method} {url}: {body}") from error


class Smoke:
    def __init__(self, wheel: Path, constraints: Path | None = None) -> None:
        self.wheel = wheel
        self.constraints = constraints
        self.failures: list[str] = []

    def check(self, name: str, fn: object) -> bool:
        print(f"[smoke] {name} ...", flush=True)
        try:
            fn()
            print(f"[smoke]   PASS: {name}", flush=True)
            return True
        except Exception as error:  # noqa: BLE001
            self.failures.append(name)
            print(f"[smoke]   FAIL: {name}: {error}", flush=True)
            return False

    def run(self) -> int:
        with tempfile.TemporaryDirectory(prefix="specflow-smoke-") as td:
            work = Path(td)
            venv = work / ".venv"
            py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            pip = venv / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
            api_dir = work / "api"
            repo_dir = api_dir / "fake-repo"
            repo_dir.mkdir(parents=True)
            (repo_dir / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
            _run([sys.executable, "-m", "venv", str(venv)])

            if not self.check("clean venv + wheel install", lambda: self._install(pip, venv)):
                print("[smoke] RESULT: FAIL (installation; runtime checks could not start)")
                return 1
            self.check("installed package identity", lambda: self._identity(py, work))
            self.check("specflow --version", lambda: self._version(py, work))
            self.check(
                "import specflow.artifacts",
                lambda: self._python(py, work, "import specflow, specflow.artifacts"),
            )
            self.check("default legacy CLI (no --mode)", lambda: self._cli(py, work, repo_dir))
            self.check("explicit legacy CLI", lambda: self._cli(py, work, repo_dir, mode="legacy"))
            self.check(
                "explicit multi-agent CLI",
                lambda: self._cli(py, work, repo_dir, mode="multi-agent"),
            )
            self.check("bundled + custom + hostile CWD prompts", lambda: self._resources(py, work))
            self.check(
                "default CLI with hostile CWD prompts",
                lambda: self._cli(py, work, repo_dir, label="hostile"),
            )
            self.check(
                "boot API + mock run + artifact read",
                lambda: self._api(work, py, api_dir, repo_dir),
            )
        if self.failures:
            print(f"[smoke] RESULT: FAIL ({len(self.failures)}): {', '.join(self.failures)}")
            return 1
        print("[smoke] RESULT: PASS")
        return 0

    def _install(self, pip: Path, venv: Path) -> None:
        if self.constraints is not None:
            # uv's export includes pinned transitive requirements and hashes.
            # Install those first; a local, newly built wheel has no lockfile hash.
            _run(
                [str(pip), "install", "--quiet", "--require-hashes", "-r", str(self.constraints)],
                cwd=venv.parent,
                env=_runtime_environment(),
            )
        command = [str(pip), "install", "--quiet"]
        if self.constraints is not None:
            command.append("--no-deps")
        _run([*command, str(self.wheel)], cwd=venv.parent, env=_runtime_environment())

    def _version(self, py: Path, work: Path) -> None:
        entry = py.parent / ("specflow.exe" if os.name == "nt" else "specflow")
        output = _run([str(entry), "--version"], cwd=work, env=_runtime_environment())
        version = self._python(
            py, work, 'from importlib.metadata import version; print(version("specflow-agent"))'
        ).strip()
        assert output.strip() == f"specflow {version}", f"unexpected version output: {output!r}"

    def _python(self, py: Path, work: Path, code: str, *args: str) -> str:
        return _run([str(py), "-I", "-c", code, *args], cwd=work, env=_runtime_environment())

    def _identity(self, py: Path, work: Path) -> None:
        output = self._python(
            py,
            work,
            """
import json, sys, specflow
from pathlib import Path
from importlib.metadata import distribution
dist = distribution('specflow-agent')
assert Path(specflow.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert Path(dist.locate_file('')).resolve().is_relative_to(Path(sys.prefix).resolve())
direct = json.loads(dist.read_text('direct_url.json'))
assert not direct.get('dir_info', {}).get('editable', False)
assert direct['url'].endswith('.whl')
print(json.dumps({'version':dist.version, 'source':'venv/site-packages', 'editable':False}))
""",
        )
        print(f"[smoke]   identity: {output.strip()}")

    def _cli(
        self, py: Path, work: Path, repo: Path, *, mode: str | None = None, label: str = "default"
    ) -> None:
        entry = py.parent / ("specflow.exe" if os.name == "nt" else "specflow")
        output = work / f"cli-{mode or label}"
        command = [
            str(entry),
            "run",
            "--repo",
            str(repo),
            "--requirement",
            "Add a health endpoint.",
            "--output",
            str(output),
            "--mock",
        ]
        if mode is not None:
            command.extend(["--mode", mode])
        _run(command, cwd=work, env=_runtime_environment())
        directories = [p for p in output.glob("run-*") if p.is_dir()]
        assert len(directories) == 1, "expected exactly one completed CLI run directory"
        directory = directories[0]
        if mode == "multi-agent":
            self._verify_multi(py, work, directory)
        else:
            self._verify_legacy(py, work, directory)

    def _verify_legacy(self, py: Path, work: Path, directory: Path) -> None:
        self._python(
            py,
            work,
            """
import json, sys
from pathlib import Path
from specflow.workers.analyze import AnalysisOutput
from specflow.workers.generate import GenerationOutput
from specflow.workers.review import ReviewOutput
root = Path(sys.argv[1])
read = lambda name: (root / name).read_text(encoding='utf-8')
manifest = json.loads(read('manifest.json'))
assert manifest['run_id'] == root.name
assert manifest['status'] == 'completed' and manifest['provider_type'] == 'mock'
assert manifest['review_decision'] == 'PASS'
assert not manifest['degraded'] and not manifest['requires_review']
analysis = AnalysisOutput.from_json(read('analysis.json'))
generation = GenerationOutput.from_json(
    read('generation.json'), analysis_hash=analysis.analysis_hash)
review = ReviewOutput.from_json(read('review.json'),
    analysis_hash=analysis.analysis_hash, generation_hash=generation.generation_hash)
assert analysis.requirement_summary.strip() and generation.proposed_solution.strip()
assert generation.implementation_steps and generation.test_plan
assert review.decision.value == 'PASS' and review.summary.strip()
assert not any([analysis.degraded, generation.degraded, review.degraded,
                review.requires_revision, review.requires_human_review])
for name in ('analysis', 'generation', 'review'):
    value = {'analysis':analysis, 'generation':generation, 'review':review}[name]
    assert manifest[name + '_hash'] == getattr(value, name + '_hash')
traces = json.loads(read('trace.json'))
assert len(traces) == 3
assert {t['metadata']['worker_role'] for t in traces} == {'analyze','generate','review'}
assert all(t['fallback_level'] == 'none' for t in traces)
for name in ('technical-spec.md','test-plan.md','run-summary.md'):
    assert read(name).strip()
""",
            str(directory),
        )

    def _verify_multi(self, py: Path, work: Path, directory: Path) -> None:
        self._python(
            py,
            work,
            """
import json, sys
from pathlib import Path
from specflow.runner_multi import _build_registry
from specflow.schema import build_schema_registry
root = Path(sys.argv[1])
read = lambda name: json.loads((root/name).read_text(encoding='utf-8'))
manifest, outputs, metrics = read('manifest.json'), read('agent-outputs.json'), read('metrics.json')
assert manifest['run_id'] == root.name and manifest['workflow_state'] == 'completed'
assert metrics['provider'] == 'mock' and metrics['review_decision'] == 'PASS'
assert metrics['schema_validated_count'] == 6 and metrics['degraded_count'] == 0
registry, schemas = _build_registry(), build_schema_registry()
assert len(outputs) == 6
for result in outputs.values():
    assert result.get('success', True) and result['schema_validated']
    identity = registry.get(result['agent_id']).identity
    schemas.get(identity.output_schema_id).model_validate(result['output'])
assert len(read('handoffs.json')) == 7
assert (root/'_COMPLETE').is_file()
""",
            str(directory),
        )

    def _resources(self, py: Path, work: Path) -> None:
        with ZipFile(self.wheel) as archive:
            expected = {
                f"{name}/{filename}": sha256(
                    archive.read(f"specflow/prompt_assets/{name}/{filename}")
                ).hexdigest()
                for name in PROMPT_NAMES
                for filename in ("template.md", "v1.0.0.yaml")
            }
        output = self._python(
            py,
            work,
            """
import json, sys
from pathlib import Path
from hashlib import sha256
from importlib import resources
from specflow.prompts import PromptRegistry, PromptNotFoundError
names = ('analyze_requirement','generate_spec','review_generation')
assets = resources.files('specflow').joinpath('prompt_assets')
actual, definitions = {}, {}
for name in names:
    definitions[name] = PromptRegistry().get(name,'1.0.0')
    assert definitions[name].render(dict.fromkeys(definitions[name].required_variables, 'fixture'))
    for filename in ('template.md','v1.0.0.yaml'):
        actual[name+'/'+filename] = sha256(assets.joinpath(name,filename).read_bytes()).hexdigest()
custom = Path('explicit-custom')
for name in names:
    (custom/name).mkdir(parents=True)
    for filename in ('template.md','v1.0.0.yaml'):
        (custom/name/filename).write_bytes(assets.joinpath(name,filename).read_bytes())
    assert PromptRegistry(custom).get(name,'1.0.0').prompt_hash == definitions[name].prompt_hash
for root, name, version in [(Path('missing-root'), names[0], '1.0.0'),
                            (custom, '../escape', '1.0.0'), (custom, names[0], '../1.0.0')]:
    try:
        PromptRegistry(root).get(name,version)
    except PromptNotFoundError:
        pass
    else:
        raise AssertionError('invalid custom lookup silently succeeded')
for name in names:
    forged = Path('prompts')/name
    forged.mkdir(parents=True)
    (forged/'v1.0.0.yaml').write_bytes(assets.joinpath(name,'v1.0.0.yaml').read_bytes())
    template = assets.joinpath(name,'template.md').read_text(encoding='utf-8')
    (forged/'template.md').write_text('FORGED CWD PROMPT\\n'+template, encoding='utf-8')
    assert 'FORGED CWD PROMPT' in PromptRegistry('prompts').get(name,'1.0.0').template
    assert PromptRegistry().get(name,'1.0.0').prompt_hash == definitions[name].prompt_hash
print(json.dumps(actual))
""",
        )
        assert json.loads(output) == expected, "installed prompt bytes differ from the exact wheel"

    def _api(self, work: Path, py: Path, api_dir: Path, repo_dir: Path) -> None:
        port = _free_port()
        environment = _server_environment(api_dir)
        server = subprocess.Popen(
            [str(py), "-m", "uvicorn", "specflow.main:app", "--port", str(port)],
            cwd=str(api_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    status, body = _http("GET", f"{base}/health")
                    expected = {"status": "ok"}
                    assert status == 200 and body == expected, f"unexpected health: {status} {body}"
                    break
                except (OSError, RuntimeError):
                    if time.monotonic() > deadline:
                        log = server.stdout.readline() if server.stdout else "(no log)"
                        message = f"API did not become healthy; server log: {log}"
                        raise RuntimeError(message) from None
                    time.sleep(0.5)

            status, project = _http(
                "POST",
                f"{base}/api/v1/projects",
                {"name": "smoke-project", "repository_path": str(repo_dir)},
            )
            assert status == 201, f"project creation failed: {status}"

            run_payload = {
                "project_id": project["id"],
                "requirement": "Add a health endpoint.",
                "mock": True,
            }
            status, run = _http("POST", f"{base}/api/v1/runs", run_payload)
            assert status == 201, f"run creation failed: {status}"

            run_id = run["id"]
            run_state = self._wait_for_run(base, run_id)
            assert run_state in {"completed", "completed_degraded"}, f"run ended in {run_state}"

            status, artifacts = _http("GET", f"{base}/api/v1/runs/{run_id}/artifacts")
            assert status == 200, f"artifacts fetch failed: {status}"
            assert artifacts.get("files"), f"no artifacts generated: {artifacts}"
            assert "manifest.json" in artifacts["files"], f"manifest missing: {artifacts}"
            self._verify_manifest(api_dir, run_id)
            directory = next((api_dir / "data" / "runs" / run_id).glob("run-multi-*"))
            self._verify_multi(py, work, directory)
            _, package = _http("GET", f"{base}/api/v1/runs/{run_id}/review-package")
            assert package, "empty completed-Run review package"
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()

    def _verify_manifest(self, api_dir: Path, api_run_id: str) -> None:
        """Read a generated artifact and verify its persisted integrity record."""
        output_root = api_dir / "data" / "runs" / api_run_id
        run_directories = sorted(
            path
            for path in output_root.glob("run-multi-*")
            if path.is_dir() and not path.is_symlink()
        )
        assert len(run_directories) == 1, f"unexpected run directories: {run_directories}"
        run_directory = run_directories[0]
        manifest_path = run_directory / "manifest.json"
        integrity_path = run_directory / "artifact-integrity.json"
        assert manifest_path.is_file() and not manifest_path.is_symlink()
        assert integrity_path.is_file() and not integrity_path.is_symlink()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
        assert manifest["run_id"] == run_directory.name
        assert manifest["workflow_state"] == "completed"
        expected_digest = integrity.get("artifact_hashes", {}).get("manifest.json")
        assert isinstance(expected_digest, str), "manifest digest missing from integrity record"
        assert sha256(manifest_path.read_bytes()).hexdigest() == expected_digest

    def _wait_for_run(self, base: str, run_id: str) -> str:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            _, run = _http("GET", f"{base}/api/v1/runs/{run_id}")
            if run.get("status") in TERMINAL_STATES:
                return run["status"]
            time.sleep(1)
        raise RuntimeError(f"run {run_id} did not finish within {TIMEOUT_SECONDS}s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wheel", help="path to a prebuilt wheel; defaults to building from the repo"
    )
    parser.add_argument("--sdist", help="also rebuild this exact sdist and smoke its wheel")
    parser.add_argument(
        "--constraints", help="locked runtime requirements (default: uv.lock export)"
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="specflow-build-smoke-") as td:
        work = Path(td)
        constraints = Path(args.constraints).resolve() if args.constraints else work / "locked.txt"
        if not args.constraints:
            _run(
                [
                    "uv",
                    "export",
                    "--frozen",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                    "--output-file",
                    str(constraints),
                ],
                cwd=REPO_ROOT,
            )
        if args.wheel:
            wheel = Path(args.wheel).resolve()
            sdist = Path(args.sdist).resolve() if args.sdist else None
        else:
            dist = work / "dist"
            _run(["uv", "build", "--out-dir", str(dist)], cwd=REPO_ROOT)
            wheel = _only_built(dist, "*.whl")
            sdist = _only_built(dist, "*.tar.gz")
        _print_identity(wheel)
        outcome = Smoke(wheel, constraints).run()
        if sdist is not None:
            _print_identity(sdist)
            source_root = work / "sdist-only"
            source_root.mkdir()
            with tarfile.open(sdist) as archive:
                archive.extractall(source_root, filter="data")
            projects = list(source_root.glob("*/pyproject.toml"))
            assert len(projects) == 1, "sdist must contain one standalone project"
            rebuilt = work / "rebuilt"
            _run(
                ["uv", "build", "--wheel", "--out-dir", str(rebuilt)],
                cwd=projects[0].parent,
                env=_runtime_environment(),
            )
            rebuilt_wheel = _only_built(rebuilt, "*.whl")
            _print_identity(rebuilt_wheel)
            print("[smoke] standalone sdist-rebuilt wheel", flush=True)
            outcome = max(outcome, Smoke(rebuilt_wheel, constraints).run())
        return outcome


def _only_built(directory: Path, pattern: str) -> Path:
    candidates = list(directory.glob(pattern))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one newly built {pattern}, found {len(candidates)}")
    return candidates[0]


def _print_identity(path: Path) -> None:
    print(
        f"[smoke] artifact: {path.name} sha256={sha256(path.read_bytes()).hexdigest()}", flush=True
    )


if __name__ == "__main__":
    raise SystemExit(main())
