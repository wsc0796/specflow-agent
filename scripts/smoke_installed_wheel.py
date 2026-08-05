"""Installed-wheel smoke: build, install into a clean venv, boot the API, run a mock workflow.

Usage:
    python scripts/smoke_installed_wheel.py
    python scripts/smoke_installed_wheel.py --wheel dist/specflow_agent-1.1.0-py3-none-any.whl
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 90

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
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        details = f"stdout: {result.stdout}\nstderr: {result.stderr}"
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{details}")
    return result.stdout


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _http(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code} on {method} {url}: {body}") from error


class Smoke:
    def __init__(self, wheel: Path) -> None:
        self.wheel = wheel
        self.failures: list[str] = []

    def check(self, name: str, fn: object) -> None:
        print(f"[smoke] {name} ...", flush=True)
        try:
            fn()
            print(f"[smoke]   PASS: {name}", flush=True)
        except Exception as error:  # noqa: BLE001
            self.failures.append(name)
            print(f"[smoke]   FAIL: {name}: {error}", flush=True)

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

            self.check("clean venv + wheel install", lambda: self._install(pip, venv))
            self.check("specflow --version", lambda: self._version(py))
            self.check(
                "import specflow.artifacts",
                lambda: _run([str(py), "-c", "import specflow, specflow.artifacts"]),
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
        _run([str(pip), "install", "--quiet", str(self.wheel)])

    def _version(self, py: Path) -> None:
        entry = py.parent / ("specflow.exe" if os.name == "nt" else "specflow")
        output = _run([str(entry), "--version"])
        assert "1.1.0" in output, f"unexpected version output: {output!r}"

    def _api(self, work: Path, py: Path, api_dir: Path, repo_dir: Path) -> None:
        port = _free_port()
        server = subprocess.Popen(
            [str(py), "-m", "uvicorn", "specflow.main:app", "--port", str(port)],
            cwd=str(api_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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
    args = parser.parse_args()

    if args.wheel:
        wheel = Path(args.wheel).resolve()
        if not wheel.exists():
            print(f"[smoke] wheel not found: {wheel}")
            return 1
    else:
        _run(["uv", "build"], cwd=REPO_ROOT)
        wheels = sorted((REPO_ROOT / "dist").glob("specflow_agent-*.whl"))
        if not wheels:
            print("[smoke] no wheel built")
            return 1
        wheel = wheels[-1]

    return Smoke(wheel).run()


if __name__ == "__main__":
    raise SystemExit(main())
