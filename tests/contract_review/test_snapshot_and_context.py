"""Fixed-object input boundaries, independent of model semantic quality."""

import copy

import pytest
from pydantic import ValidationError

from specflow.contract_review.common import ReviewError
from specflow.contract_review.inputs import match_scope
from specflow.contract_review.schemas import CreateReview, GitSource
from specflow.contract_review.sources import GitSnapshotReader, SnapshotLimits


def reader_for(root, **limits):
    def validate(path):
        if not path.resolve().is_relative_to(root.parent.resolve()):
            raise ReviewError("REPOSITORY_PATH_FORBIDDEN", "Outside fixture", 403)

    return GitSnapshotReader(validate, SnapshotLimits(**limits))


def test_reads_original_commit_bytes_despite_dirty_worktree_and_replacement(git_repo):
    root, git, request = git_repo
    source = GitSource.model_validate(request["source"])
    original = (root / "docs/api.md").read_bytes()
    old = git("rev-parse", source.commit_sha + ":docs/api.md")
    replacement = git("hash-object", "-w", "--stdin", data=b"replacement\n")
    git("replace", old, replacement)
    (root / "docs/api.md").write_bytes(b"uncommitted\r\n")
    snapshot = reader_for(root).prepare(str(root), source)
    assert (
        next(item for item in snapshot["files"] if item["path"] == "docs/api.md")["body"].encode()
        == original
    )


def test_source_size_rejected_before_reading_body(git_repo):
    root, _, request = git_repo
    with pytest.raises(ReviewError) as caught:
        reader_for(root, file_bytes=8).prepare(
            str(root), GitSource.model_validate(request["source"])
        )
    assert caught.value.code == "SOURCE_TOO_LARGE"


def test_missing_object_does_not_silently_use_worktree(git_repo):
    root, _, request = git_repo
    request["source"]["commit_sha"] = "0" * 40
    with pytest.raises(ReviewError) as caught:
        reader_for(root).prepare(str(root), GitSource.model_validate(request["source"]))
    assert caught.value.code == "INVALID_SOURCE"


@pytest.mark.parametrize("kind", ["lfs", "binary", "invalid_utf8", "symlink"])
def test_unsupported_selected_source_is_rejected_without_silent_skip(git_repo, kind):
    root, git, request = git_repo
    contents = {
        "lfs": b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\n",
        "binary": b"abc\x00xyz",
        "invalid_utf8": b"\xff",
        "symlink": b"outside.md",
    }
    oid = git("hash-object", "-w", "--stdin", data=contents[kind])
    mode = "120000" if kind == "symlink" else "100644"
    git("update-index", "--add", "--cacheinfo", f"{mode},{oid},docs/api.md")
    git("commit", "-qm", kind)
    request["source"]["commit_sha"] = git("rev-parse", "HEAD")
    with pytest.raises(ReviewError) as caught:
        reader_for(root).prepare(str(root), GitSource.model_validate(request["source"]))
    assert caught.value.code == "UNSUPPORTED_SOURCE"


@pytest.mark.parametrize(
    "mutation", ["null", "boolean_line", "extra", "duplicate_check", "traversal"]
)
def test_strict_input_rejects_ambiguous_fields(git_repo, mutation):
    _, _, original = git_repo
    body = copy.deepcopy(original)
    if mutation == "null":
        body["targets"][0]["endpoint"] = None
    elif mutation == "boolean_line":
        body["authority_bindings"][0]["selector"] = {
            "kind": "lines",
            "start_line": True,
            "end_line": 2,
        }
    elif mutation == "extra":
        body["job_id"] = "forged"
    elif mutation == "duplicate_check":
        body["targets"][0]["checks"] *= 2
    else:
        body["source"]["groups"][0]["paths"] = ["../secret.md"]
    with pytest.raises(ValidationError):
        CreateReview.model_validate(body)


def test_scope_requires_one_target_to_satisfy_all_dimensions():
    endpoint = {"method": "POST", "path": "/exports"}
    scope = {"api_versions": ["v2"], "endpoints": [endpoint], "source_paths": ["docs/a.md"]}
    assert match_scope(scope, {"api_version": "v2", "endpoint": endpoint}) == "scope_unresolved"
    assert (
        match_scope(scope, {"api_version": "v2", "endpoint": endpoint, "source_path": "src/a.py"})
        == "no_match"
    )
    assert (
        match_scope(scope, {"api_version": "v2", "endpoint": endpoint, "source_path": "docs/a.md"})
        == "match"
    )
