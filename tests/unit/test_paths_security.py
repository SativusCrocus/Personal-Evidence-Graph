from __future__ import annotations

from pathlib import Path

import pytest

from app.security.paths import PathSafetyError, resolve_inside, safe_filename


def test_resolves_inside_root(tmp_path: Path):
    target = tmp_path / "sub" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("hi")
    out = resolve_inside([tmp_path], target)
    assert out == target.resolve()


def test_blocks_traversal(tmp_path: Path):
    inside = tmp_path / "jail"
    inside.mkdir()
    bad = inside / ".." / ".." / "etc" / "passwd"
    with pytest.raises(PathSafetyError):
        resolve_inside([inside], bad)


def test_blocks_absolute_outside(tmp_path: Path):
    inside = tmp_path / "jail"
    inside.mkdir()
    with pytest.raises(PathSafetyError):
        resolve_inside([inside], "/etc/hosts")


def test_blocks_empty_path(tmp_path: Path):
    with pytest.raises(PathSafetyError):
        resolve_inside([tmp_path], "")


def test_safe_filename_strips_dangerous():
    assert safe_filename("../../etc/passwd") == "______etc_passwd"
    assert safe_filename("file:name?.pdf") == "file_name_.pdf"
    assert safe_filename("") == "untitled"
    assert safe_filename("   ") == "untitled"


def test_safe_filename_truncates():
    long = "a" * 500 + ".pdf"
    out = safe_filename(long, max_len=200)
    assert len(out) <= 200
    assert out.endswith(".pdf")
