"""CR02 TASK-00 environment evidence; never opens product data or a provider."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path


def windows_process_exit_probe() -> str:
    """Check the native evidence needed to distinguish a PID from an instance."""
    if os.name != "nt":
        return "NOT_APPLICABLE"
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    handle = kernel.OpenProcess(0x00100000 | 0x1000, False, child.pid)
    try:
        assert handle
        times = [wintypes.FILETIME() for _ in range(4)]
        assert kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times])
        assert times[0].dwHighDateTime > 0
        assert kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT: still live
        child.communicate(b"x", timeout=10)
        assert kernel.WaitForSingleObject(handle, 0) == 0  # process object signalled
    finally:
        if child.poll() is None:
            child.communicate(b"x", timeout=10)
        if handle:
            kernel.CloseHandle(handle)
    return "PASS"


def probe(root: Path) -> dict:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_NAME="Environment probe",
        GIT_AUTHOR_EMAIL="probe@example.invalid",
        GIT_COMMITTER_NAME="Environment probe",
        GIT_COMMITTER_EMAIL="probe@example.invalid",
    )
    repo = root / "repo"
    repo.mkdir()

    def git(*args: str, data: bytes | None = None, safe: bool = True, check: bool = True):
        flags = ["--no-replace-objects", "--no-lazy-fetch"] if safe else []
        return subprocess.run(
            ["git", *flags, "-c", "protocol.allow=never", "-C", str(repo), *args],
            input=data,
            capture_output=True,
            check=check,
            timeout=10,
            env=env,
        )

    git("init", "-q")
    original = git("hash-object", "-w", "--stdin", data=b"original\r\n").stdout.strip()
    replacement = git("hash-object", "-w", "--stdin", data=b"replacement\n").stdout.strip()
    git("replace", original.decode(), replacement.decode())
    assert git("cat-file", "blob", original.decode(), safe=False).stdout == b"replacement\n"
    assert git("cat-file", "blob", original.decode()).stdout == b"original\r\n"
    tree = git("mktree", data=b"100644 blob " + original + b"\tsource.md\n").stdout.strip()
    commit = git("commit-tree", tree.decode(), data=b"probe\n").stdout.strip()
    assert git("cat-file", "-t", commit.decode()).stdout == b"commit\n"
    assert git("cat-file", "-s", original.decode()).stdout == b"10\n"
    paths = {
        key: git("rev-parse", "--path-format=absolute", flag).stdout.decode().strip()
        for key, flag in (("git_dir", "--git-dir"), ("common_dir", "--git-common-dir"))
    }
    assert all(Path(value).resolve().is_relative_to(repo.resolve()) for value in paths.values())

    # A promisor repository advertises an absent blob. Trace proves no fetch child
    # was started; protocol.allow=never is an additional network denial boundary.
    git("config", "extensions.partialClone", "origin")
    git("config", "remote.origin.promisor", "true")
    git("config", "remote.origin.url", "https://example.invalid/never-fetch.git")
    git("replace", "-d", original.decode())
    object_path = repo / ".git" / "objects" / original[:2].decode() / original[2:].decode()
    assert object_path.resolve().is_relative_to(root.resolve())
    object_path.chmod(stat.S_IWRITE | stat.S_IREAD)
    object_path.unlink()
    trace = root / "git-trace.jsonl"
    env["GIT_TRACE2_EVENT"] = str(trace)
    missing = git("cat-file", "-s", original.decode(), check=False)
    assert missing.returncode != 0
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert not any(event["event"] == "child_start" for event in events)

    db_path = root / "probe.sqlite"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            "CREATE TABLE reviews(id TEXT PRIMARY KEY, version INTEGER NOT NULL);"
            "CREATE TABLE jobs(id TEXT PRIMARY KEY, review_id TEXT, state TEXT);"
            "CREATE UNIQUE INDEX one_active ON jobs(review_id) "
            "WHERE state IN ('queued','running');"
            "INSERT INTO reviews VALUES ('r',1);"
        )
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO jobs VALUES ('j','r','queued')")
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("UPDATE reviews SET version=2 WHERE id='r' AND version=1").rowcount == 1
        assert conn.execute("UPDATE reviews SET version=3 WHERE id='r' AND version=1").rowcount == 0
        conn.execute("INSERT INTO jobs VALUES ('j','r','queued')")
        try:
            conn.execute("INSERT INTO jobs VALUES ('j2','r','running')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("partial unique index did not protect active job")

    lock_path = root / "instance.lock"
    lock_path.write_bytes(b"0")
    child = (
        "import msvcrt,sys; f=open(sys.argv[1],'r+b'); msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)"
        if os.name == "nt"
        else "import fcntl,sys; f=open(sys.argv[1],'r+b'); "
        "fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
    )
    with lock_path.open("r+b") as handle:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        denied = subprocess.run(
            [sys.executable, "-c", child, str(lock_path)], capture_output=True, timeout=10
        )
        assert denied.returncode != 0
    acquired = subprocess.run(
        [sys.executable, "-c", child, str(lock_path)], capture_output=True, timeout=10
    )
    assert acquired.returncode == 0
    return {
        "kind": "environment_probe_not_product_acceptance",
        "git_version": git("--version").stdout.decode().strip(),
        "python": sys.version.split()[0],
        "checks": {
            "replacement_disabled_original_bytes_preserved": "PASS",
            "missing_promisor_blob_no_fetch_child": "PASS",
            "git_and_common_dir_absolute_boundary": "PASS",
            "sqlite_rollback_cas_partial_unique_index": "PASS",
            "os_exclusive_lock_cross_process_and_release": "PASS",
            "windows_process_creation_identity_and_exit_signal": windows_process_exit_probe(),
        },
        "model_calls": 0,
        "product_ac_status": "NOT_RUN",
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="specflow-cr02-probe-") as directory:
        result = probe(Path(directory))
    print(json.dumps(result, ensure_ascii=False, indent=2))
