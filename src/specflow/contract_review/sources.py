"""Bounded, offline Git-object preparation. No checkout or source execution."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from specflow.contract_review.common import ReviewError, digest, identity
from specflow.contract_review.schemas import GitSource


@dataclass(frozen=True)
class SnapshotLimits:
    files: int = 1000
    file_bytes: int = 1024 * 1024
    total_bytes: int = 20 * 1024 * 1024
    seconds: float = 30


def strict_json(body: str):
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key")
            value[key] = item
        return value

    def invalid_constant(_):
        raise ValueError("Non-finite JSON number")

    return json.loads(body, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def select_text(text: str, selector: dict) -> str:
    try:
        if selector["kind"] == "full":
            return text
        if selector["kind"] == "lines":
            lines = text.splitlines(keepends=True)
            start, end = selector["start_line"], selector["end_line"]
            if start < 1 or end < start or end > len(lines):
                raise ValueError("Line range is outside the source")
            return "".join(lines[start - 1 : end])
        value = strict_json(text)
        pointer = selector["pointer"]
        for part in pointer.split("/")[1:] if pointer else []:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if (
                    not part.isascii()
                    or not part.isdigit()
                    or (part != "0" and part.startswith("0"))
                ):
                    raise ValueError("Invalid array index")
                value = value[int(part)]
            elif isinstance(value, dict):
                value = value[part]
            else:
                raise ValueError("Pointer crosses a scalar")
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ReviewError("INVALID_AUTHORITY_BINDING", "来源片段不可用。", 422) from error


class GitSnapshotReader:
    def __init__(self, validate_path, limits: SnapshotLimits | None = None):
        self.validate_path = validate_path
        self.limits = limits or SnapshotLimits()
        self._preparing = threading.Lock()

    def prepare(self, repository: str, source: GitSource) -> dict:
        if not self._preparing.acquire(blocking=False):
            raise ReviewError("SNAPSHOT_PREPARATION_BUSY", "已有快照正在准备。", 429)
        try:
            root = Path(repository).resolve(strict=True)
            self.validate_path(root)
            return self._prepare(root, source)
        except (FileNotFoundError, NotADirectoryError) as error:
            raise ReviewError("INVALID_SOURCE", "仓库来源不可用。", 422) from error
        finally:
            self._preparing.release()

    def _prepare(self, root: Path, source: GitSource) -> dict:
        deadline = time.monotonic() + self.limits.seconds
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")

        def git(args: list[str], cap: int) -> bytes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ReviewError("SOURCE_PREPARATION_TIMEOUT", "准备快照超时。", 503)
            try:
                process = subprocess.Popen(
                    [
                        "git",
                        "--no-replace-objects",
                        "--no-lazy-fetch",
                        "--literal-pathspecs",
                        "-c",
                        "protocol.allow=never",
                        "-C",
                        str(root),
                        *args,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except OSError as error:
                raise ReviewError("DEPENDENCY_UNAVAILABLE", "Git 对象读取不可用。", 503) from error
            chunks, oversized = [], threading.Event()

            def read():
                count = 0
                while block := process.stdout.read(min(65536, cap + 1)):
                    count += len(block)
                    if count > cap:
                        oversized.set()
                        process.kill()
                        break
                    chunks.append(block)

            reader = threading.Thread(target=read)
            reader.start()
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as error:
                process.kill()
                raise ReviewError("SOURCE_PREPARATION_TIMEOUT", "准备快照超时。", 503) from error
            finally:
                process.wait()
                reader.join()
                process.stdout.close()
            if oversized.is_set():
                raise ReviewError("SOURCE_TOO_LARGE", "Git 对象输出超过上限。", 413)
            if process.returncode != 0:
                raise ReviewError("INVALID_SOURCE", "固定 Git 对象不存在或无法离线读取。", 422)
            return b"".join(chunks)

        metadata_roots = []
        for option in ("--git-dir", "--git-common-dir"):
            metadata = git(["rev-parse", "--path-format=absolute", option], 4096)
            directory = Path(os.fsdecode(metadata).strip()).resolve(strict=True)
            self.validate_path(directory)
            metadata_roots.append(directory)
        objects = (metadata_roots[-1] / "objects").resolve(strict=True)
        self.validate_path(objects)
        info = (objects / "info").resolve()
        self.validate_path(info)
        if os.path.lexists(info / "alternates"):
            raise ReviewError("UNSUPPORTED_SOURCE", "当前不支持带替代对象库的 Git 来源。", 422)
        if git(["cat-file", "-t", source.commit_sha], 32) != b"commit\n":
            raise ReviewError("INVALID_SOURCE", "来源必须是完整 commit 对象。", 422)
        selected: dict[str, dict] = {}
        for group in source.groups:
            for selection in group.paths:
                output = git(
                    ["ls-tree", "-r", "-z", source.commit_sha, "--", selection],
                    (self.limits.files + 1) * 1200,
                )
                if not output:
                    raise ReviewError("INVALID_SOURCE", "选择的来源路径不存在。", 422)
                for entry in output.rstrip(b"\x00").split(b"\x00"):
                    meta, path_bytes = entry.split(b"\t", 1)
                    mode, kind, oid = meta.decode("ascii").split(" ")
                    try:
                        path = path_bytes.decode("utf-8")
                    except UnicodeError as error:
                        raise ReviewError(
                            "UNSUPPORTED_SOURCE", "来源路径不是 UTF-8。", 422
                        ) from error
                    if mode not in ("100644", "100755") or kind != "blob":
                        raise ReviewError("UNSUPPORTED_SOURCE", "不支持链接或子模块来源。", 422)
                    if Path(path).suffix.lower() not in (".py", ".json", ".md", ".markdown"):
                        raise ReviewError("UNSUPPORTED_SOURCE", "不支持所选文件类型。", 422)
                    if len(path) > 1024:
                        raise ReviewError("UNSUPPORTED_SOURCE", "来源路径过长。", 422)
                    item = selected.setdefault(path, {"git_blob_oid": oid, "roles": set()})
                    item["roles"].add(group.role)
                    if len(selected) > self.limits.files:
                        raise ReviewError("SOURCE_TOO_LARGE", "快照文件数量超过上限。", 413)
        total, files = 0, []
        for path, item in sorted(selected.items()):
            size = int(git(["cat-file", "-s", item["git_blob_oid"]], 32))
            total += size
            if size > self.limits.file_bytes or total > self.limits.total_bytes:
                raise ReviewError("SOURCE_TOO_LARGE", "快照原始字节超过上限。", 413)
            body = git(["cat-file", "blob", item["git_blob_oid"]], self.limits.file_bytes)
            if len(body) != size:
                raise ReviewError("INVALID_SOURCE", "来源大小发生变化。", 422)
            try:
                text = body.decode("utf-8")
            except UnicodeError as error:
                raise ReviewError("UNSUPPORTED_SOURCE", "来源不是 UTF-8 文本。", 422) from error
            if "\x00" in text or text.startswith("version https://git-lfs.github.com/spec/v1"):
                raise ReviewError("UNSUPPORTED_SOURCE", "不支持二进制或 LFS 指针来源。", 422)
            files.append(
                {
                    "source_id": identity("src"),
                    "path": path,
                    "roles": sorted(item["roles"]),
                    "git_blob_oid": item["git_blob_oid"],
                    "body_hash": digest(body),
                    "byte_count": size,
                    "encoding": "utf-8",
                    "body": text,
                }
            )
        return {
            "snapshot_id": identity("snap"),
            "commit_sha": source.commit_sha,
            "selection": source.model_dump(),
            "excluded": [],
            "byte_count": total,
            "files": files,
        }
