# test_app_settings.py - persisted paths must not become folders on the wrong OS.

from pathlib import Path

from dampf.app_settings import load_settings, stored_path_for_this_os


def test_windows_drive_path_dropped_on_posix(monkeypatch):
    monkeypatch.setattr("dampf.app_settings.os.name", "posix")
    weird = "C:\\DATEN\\KPs\\Measuremement_New_Schema\\_index"
    assert stored_path_for_this_os(weird) == ""
    assert stored_path_for_this_os("/home/pm/Cursor/WETTER-Suite/datasets/pure_Testset") == (
        "/home/pm/Cursor/WETTER-Suite/datasets/pure_Testset"
    )
    assert stored_path_for_this_os("  ") == ""


def test_windows_drive_path_kept_on_windows(monkeypatch):
    monkeypatch.setattr("dampf.app_settings.os.name", "nt")
    weird = "C:\\DATEN\\KPs\\Measuremement_New_Schema\\_index"
    assert stored_path_for_this_os(weird) == weird


def test_load_settings_drops_foreign_paths(tmp_path, monkeypatch):
    ini = tmp_path / "dampf.ini"
    ini.write_text(
        "\n".join(
            [
                "[paths]",
                "root_dir = /data/set",
                "output_dir = C:\\DATEN\\KPs\\Measuremement_New_Schema\\_index",
                "db_path = C:\\DATEN\\KPs\\Measuremement_New_Schema\\Measuremement_New_Schema.db",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("dampf.app_settings.os.name", "posix")
    loaded = load_settings()
    assert loaded["root_dir"] == "/data/set"
    assert loaded["output_dir"] == ""
    assert loaded["db_path"] == ""
    assert Path.cwd() == tmp_path
