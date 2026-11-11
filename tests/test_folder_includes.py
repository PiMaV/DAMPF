# tests/test_folder_includes.py — folder Include filter semantics

from dampf.gui import filter_rows_by_folder_includes


def _row(relpath: str, ext: str = ".img") -> dict:
    return {"relpath": relpath, "ext": ext}


def test_folder_includes_none_means_all():
    rows = [_row("a/1.img"), _row("b/2.img")]
    assert filter_rows_by_folder_includes(rows, None) == rows


def test_folder_includes_empty_means_none():
    rows = [_row("a/1.img"), _row("b/2.img")]
    assert filter_rows_by_folder_includes(rows, set()) == []


def test_folder_includes_parent_covers_children():
    rows = [
        _row("1_jet/x.img"),
        _row("2_jet/y.img"),
        _row("pure/1 jet/a.img"),
        _row("pure/2 jet/b.img"),
    ]
    out = filter_rows_by_folder_includes(rows, {"1_jet", "2_jet"})
    assert [r["relpath"] for r in out] == ["1_jet/x.img", "2_jet/y.img"]


def test_unchecking_parent_path_excludes_nested():
    """If only sibling folders stay included, pure/* drops out (10800 → fewer)."""
    rows = [
        _row("1_jet/x.img"),
        _row("pure/1 jet/a.img"),
        _row("pure/2 jet/b.img"),
    ]
    out = filter_rows_by_folder_includes(rows, {"1_jet"})
    assert [r["relpath"] for r in out] == ["1_jet/x.img"]
