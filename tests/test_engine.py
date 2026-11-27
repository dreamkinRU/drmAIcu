# tests/test_engine.py
import asyncio
import time
import importlib
import json
import re
import os
import pytest

main = importlib.import_module("main")
import patch_engine as engine
import agent_engine
import guards
from api import shared
from api import routes_patches as rpat
from api import routes_project as rp
from api import routes_providers as rprov
from api import routes_system as rsys


@pytest.fixture
def box(tmp_path, monkeypatch):
    base = tmp_path / "proj"
    (base / "patch" / "archive").mkdir(parents=True)
    (base / "backups").mkdir()
    (base / "project_archive").mkdir()
    monkeypatch.setattr(engine, "BASE", str(base))
    monkeypatch.setattr(engine, "PATCH_DIR", str(base / "patch"))
    monkeypatch.setattr(engine, "ARCHIVE_DIR", str(base / "patch" / "archive"))
    monkeypatch.setattr(engine, "BACKUP_DIR", str(base / "backups"))
    monkeypatch.setattr(rp, "PROJ_ARCHIVE", str(base / "project_archive"))
    monkeypatch.setattr(engine, "MANIFEST", str(base / "patch_manifest.json"))
    monkeypatch.setattr(engine, "JOURNAL", str(base / "patch_journal.json"))
    monkeypatch.setattr(rp, "IMPORTANT", str(base / ".project-important.json"))
    monkeypatch.setattr(rp, "PROJECT_HISTORY_FILE", str(base / ".project-history.json"))
    monkeypatch.setattr(rp, "PROJECT_HISTORY", [])
    return base


def put(base, rel, text):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def read(p):
    return p.read_text(encoding="utf-8")


# ---------- БАЗА: должно проходить ----------

def test_OK_search_replace_crlf():
    out = engine.apply_search_replace("l1\r\nl2\r\nl3\r\n", "l2\n", "L2\n")
    assert out == "l1\r\nL2\r\nl3\r\n"


def test_OK_search_replace_ambiguous():
    with pytest.raises(ValueError):
        engine.apply_search_replace("a\na\n", "a", "b")


def test_OK_diff_basic():
    assert engine.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\n a\n-b\n+B") == "a\nB\nc"


def test_OK_diff_idempotent():
    d = "@@ -1,3 +1,3 @@\n a\n-b\n+B"
    once = engine.apply_diff("a\nb\nc", d)
    assert engine.apply_diff(once, d) == once


def test_OK_create_rejects_existing(box):
    put(box, "x.py", "a = 1\n")
    _, _, _, err = engine.compute_new(
        {"type": "create", "target_file": "x.py", "full_file_content": "b = 2\n"}
    )
    assert err is not None


def test_OK_phase1_blocks_everything(box):
    put(box, "good.py", "a = 1\n")
    res = engine.apply_patch({"patch_id": "T1", "operations": [
        {"type": "full_replace", "target_file": "good.py", "full_file_content": "a = 2\n"},
        {"type": "full_replace", "target_file": "bad.py", "full_file_content": "def f(:\n"},
    ]})
    assert res["success"] is False
    assert read(box / "good.py") == "a = 1\n"
    assert not (box / "bad.py").exists()


def test_OK_multi_apply_and_rollback(box):
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    assert engine.apply_patch({"patch_id": "T2", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})["success"]
    assert engine.rollback()["success"]
    assert read(box / "a.py") == "x = 1\n"
    assert read(box / "b.py") == "y = 1\n"


# ---------- БАГИ: должно ПАДАТЬ на текущем коде ----------

def test_BUG01_diff_trailing_newline():
    """B1: хвостовой \n превращается в фантомную пустую строку контекста."""
    assert engine.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n") == "a\nB\nc"


def test_BUG02_diff_crlf_injection():
    """B2: apply_diff не нормализует CRLF -> \\r остаётся в файле."""
    out = engine.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\r\n a\r\n-b\r\n+B")
    assert "\r" not in out


def test_BUG03_pure_insert_position():
    """B3: @@ -2,0 @@ = вставить ПОСЛЕ строки 2, а не до."""
    assert engine.apply_diff("l1\nl2\nl3", "@@ -2,0 +3,1 @@\n+INSERTED") == "l1\nl2\nINSERTED\nl3"


def test_BUG04_silent_skip_unmatched_hunk():
    """B4: old не найден, new найден в другом месте -> молчаливый пропуск."""
    with pytest.raises(ValueError):
        engine.apply_diff("x\na\nb", "@@ -2,2 +2,1 @@\n a\n-ZZZ")


def test_BUG05_silent_skip_pure_delete():
    """B5: пустой new_block -> find_block возвращает hint -> пропуск всегда."""
    with pytest.raises(ValueError):
        engine.apply_diff("a\nb", "@@ -1,2 +1,0 @@\n-a\n-ZZZ")


def test_BUG06_backup_basename_collision(box):
    """B6: src/App.tsx и public/App.tsx пишутся в один и тот же .bak."""
    b1 = engine.backup(str(put(box, "src/App.tsx", "SRC")))
    b2 = engine.backup(str(put(box, "public/App.tsx", "PUB")))
    assert set(b1).isdisjoint(set(b2))


def test_BUG07_failed_file_not_rolled_back(box, monkeypatch):
    """B7: файл, не прошедший SHA-проверку, отсутствует в written -> не откатывается."""
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    real, n = engine.sha_bytes, {"i": 0}

    def fake(data):
        n["i"] += 1
        return "bogus" if n["i"] > 2 else real(data)

    monkeypatch.setattr(engine, "sha_bytes", fake)
    res = engine.apply_patch({"patch_id": "T3", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})
    assert res["success"] is False
    assert read(box / "a.py") == "x = 1\n"


def test_BUG08_tsx_not_validated():
    """B8: сломанный TSX проходит валидацию."""
    ok, _ = engine.validate("src/App.tsx", "const x = ((( ;")
    assert ok is False


def test_BUG09_path_escape(box):
    """B9: target_file выходит за пределы проекта."""
    _, _, _, err = engine.compute_new(
        {"type": "create", "target_file": "../escaped.py", "full_file_content": "p = 1\n"}
    )
    assert err is not None


def test_BUG10_backups_marked_critical():
    """B10: backups/ в CRIT_DIRS -> очистка никогда их не удалит."""
    assert rp.category("App.tsx_1.bak", "backups/App.tsx_1.bak", 100) == "backup"


def test_BUG11_newline_rewrite_on_windows(box):
    """B11: LF-файл перезаписывается как CRLF, SHA-проверка это не ловит."""
    put(box, "a.py", "x = 1\ny = 2\n")
    assert engine.apply_patch({"patch_id": "T4", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 1\ny = 3\n"},
    ]})["success"]
    assert (box / "a.py").read_bytes() == b"x = 1\ny = 3\n"


def test_BUG18_multi_ops_same_file(box):
    """B18: two ops on one file must accumulate, not overwrite."""
    put(box, "a.py", "x = 1\ny = 1\n")
    res = engine.apply_patch({"patch_id": "T5", "operations": [
        {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
        {"type": "search_and_replace", "target_file": "a.py", "find": "y = 1", "replace": "y = 2"},
    ]})
    assert res["success"]
    assert read(box / "a.py") == "x = 2\ny = 2\n"

# ---------- B20-B24: движок 3.6.0 (fix PATCHES) ----------

def test_BUG20_expected_sha_mismatch_rejected(box):
    """B20: expected_sha не совпал с содержимым на диске -> патч отвергнут целиком."""
    put(box, "a.py", "x = 1\n")
    res = engine.apply_patch({"patch_id": "T-B20", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n",
         "expected_sha": "deadbeef"},
    ]})
    assert res["success"] is False
    assert "expected_sha" in res["error"]
    assert read(box / "a.py") == "x = 1\n"


def test_BUG20b_expected_sha_match_applies(box):
    """B20: корректный expected_sha пропускает патч."""
    put(box, "a.py", "x = 1\n")
    good = engine.sha_bytes(b"x = 1\n")
    res = engine.apply_patch({"patch_id": "T-B20b", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n",
         "expected_sha": good},
    ]})
    assert res["success"] is True
    assert read(box / "a.py") == "x = 2\n"


def test_BUG21_stale_file_aborts_patch_after_backup(box):
    """B21: файл изменён на диске ПОСЛЕ фазы расчёта -> патч отвергнут до записи."""
    put(box, "a.py", "x = 1\n")
    real = engine.sha_bytes
    calls = {"n": 0}

    def fake(data):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(data)
        return real(b"tampered")

    monkey = __import__("pytest").MonkeyPatch()
    monkey.setattr(engine, "sha_bytes", fake)
    try:
        res = engine.apply_patch({"patch_id": "T-B21", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        ]})
    finally:
        monkey.undo()
    assert res["success"] is False
    assert "stale" in res["error"] or "изменился" in res["error"]
    assert read(box / "a.py") == "x = 1\n"


def test_BUG22_rollback_rejects_manifest_traversal(box):
    """B22: tampered-манифест с ../ в target_file -> откат запрещён, файл не удалён."""
    put(box, "victim.txt", "do not delete\n")
    engine.save_manifest({'applied': [{'patch_id': 'EVIL', 'operations': [
        {'target_file': '../victim.txt', 'backups': []},
    ]}], 'history': [], 'rollbacks': []})
    res = engine.rollback()
    assert res["success"] is False
    assert (box / "victim.txt").exists()


def test_BUG23_stats_endpoint_not_shadowed():
    """B23: /api/patches/stats файлов регистрируется ровно один раз, s_pstats жив."""
    stats_routes = [r for router in main.app._iter_routers() for r in router.routes if getattr(r, 'path', '') == '/api/patches/stats']
    assert len(stats_routes) == 1
    handler = getattr(stats_routes[0], 'endpoint', None)
    assert handler is rpat.s_pstats


def test_BUG24_tx_lock_serializes_toggle():
    """B24: TX_LOCK существует и является RLock (apply/rollback сериализуются)."""
    got = []
    def hold_in_subthread():
        if engine.TX_LOCK.acquire(timeout=2):
            got.append(True)
            import time; time.sleep(0.3)
            engine.TX_LOCK.release()
    import threading as th
    t = th.Thread(target=hold_in_subthread)
    t.start()
    t.join(2)
    assert got == [True]
    assert engine.TX_LOCK.acquire(timeout=2)
    engine.TX_LOCK.release()


def test_engine_module_is_ui_free():
    """patch_engine импортируется в чистом интерпретаторе без nicegui/fastapi."""
    import subprocess, sys as _sys
    code = (
        "import sys; import patch_engine; "
        "leaks = [m for m in ('nicegui', 'uvicorn', 'fastapi') if m in sys.modules]; "
        "print('LEAKS:' + ','.join(leaks))"
    )
    r = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "LEAKS:" in r.stdout and r.stdout.strip().split("LEAKS:")[1] == "", r.stdout


# ---------- B25-B29: волна 1 — оборона производства патчей ----------

def test_B25_patch_filename_traversal_rejected(box):
    outside = box.parent
    payload = {"patch_id": "EVIL25", "operations": [
        {"type": "create", "target_file": "pwned.py", "full_file_content": "p = 1\n"}
    ]}
    (outside / "evil.json").write_text(__import__("json").dumps(payload), encoding="utf-8")
    res = engine.apply_patch({"patch_id": "EVIL25", "filename": "../../evil.json"})
    assert res.get("success") is False
    assert not (box / "pwned.py").exists()
    assert (outside / "evil.json").read_text(encoding="utf-8") == __import__("json").dumps(payload)


def test_B25b_patch_body_from_disk_still_works(box):
    import json as _json
    put(box, "a.py", "x = 1\n")
    (box / "patch" / "B25BODY.json").write_text(_json.dumps({
        "patch_id": "B25BODY",
        "operations": [{"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}]
    }), encoding="utf-8")
    res = engine.apply_patch({"patch_id": "B25BODY"})
    assert res["success"]
    assert read(box / "a.py") == "x = 2\n"


def test_patch_progress_reports_actual_stage_and_result(box, monkeypatch):
    monkeypatch.setattr(engine, "DOWNLOADS_DIR", "")
    put(box, "status.txt", "old")
    observed = []
    original = engine.backup
    def observe(path):
        observed.append(engine.patch_progress())
        return original(path)
    monkeypatch.setattr(engine, "backup", observe)
    result = engine.apply_patch({"patch_id": "STATUS1", "operations": [
        {"type": "full_replace", "target_file": "status.txt", "full_file_content": "new"}]})
    assert result["success"]
    assert observed[0]["state"] == "running"
    assert observed[0]["stage"] == "backup"
    assert observed[0]["total"] == 1
    assert engine.patch_progress()["state"] == "warning"
    assert engine.patch_progress()["done"] == 1
    assert not engine.apply_patch({"patch_id": "STATUS1"})["success"]
    assert engine.patch_progress()["state"] == "failed"


def test_patch_txt_downloads_archive_and_persistent_report(box, monkeypatch):
    downloads = box / "downloads"
    downloads.mkdir()
    monkeypatch.setattr(engine, "DOWNLOADS_DIR", str(downloads))
    put(box, "a.txt", "old")
    data = {"patch_id": "TXT1", "operations": [{"type": "full_replace", "target_file": "a.txt", "full_file_content": "new"}]}
    src = downloads / "TXT1.TXT"
    src.write_text(json.dumps(data), encoding="utf-8-sig")
    (downloads / "notes.txt").write_text("ordinary notes", encoding="utf-8")
    assert [p["filename"] for p in engine.list_patches()] == ["TXT1.TXT"]
    (box / "patch" / "archive" / src.name).write_text("old archive", encoding="utf-8")
    result = engine.apply_patch({"patch_id": "TXT1", "filename": src.name})
    assert result["success"] and result["report"]["archive_status"] == "archived"
    assert not src.exists()
    assert (box / "patch" / "archive" / src.name).read_text(encoding="utf-8") == "old archive"
    assert engine.stats()["reports"][0]["archive_status"] == "archived"
    assert engine.stats()["applied"] == 1


def test_patch_archive_failure_does_not_repeat_apply(box, monkeypatch):
    monkeypatch.setattr(engine, "DOWNLOADS_DIR", "")
    put(box, "a.txt", "old")
    data = {"patch_id": "LOCKED", "operations": [{"type": "full_replace", "target_file": "a.txt", "full_file_content": "new"}]}
    src = box / "patch" / "locked.txt"
    src.write_text(json.dumps(data), encoding="utf-8")
    def fail(*args):
        raise PermissionError("locked")
    monkeypatch.setattr(engine.shutil, "move", fail)
    result = engine.apply_patch({"patch_id": "LOCKED", "filename": src.name})
    assert result["success"] and result["report"]["archive_status"] == "failed"
    assert src.exists() and read(box / "a.txt") == "new"
    assert engine.list_patches()[0]["is_applied"]
    assert engine.stats()["pending"] == 0
    assert not engine.apply_patch(data)["success"]


def test_patch_txt_does_not_select_unrelated_file(box, monkeypatch):
    monkeypatch.setattr(engine, "DOWNLOADS_DIR", "")
    src = box / "patch" / "notes.txt"
    src.write_text("ordinary notes", encoding="utf-8")
    assert engine.find_patch_file("", src.name) is None
    assert not json.loads(rpat.s_pdel({"filename": src.name}).body)["success"]
    assert src.exists()


def test_B26_manifest_write_crash_keeps_old_state(box, monkeypatch):
    import json as _json
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch({"patch_id": "B26-SETUP", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    before = (box / "patch_manifest.json").read_text(encoding="utf-8")
    real_dump = _json.dump
    def exploding_dump(obj, fp, *a, **kw):
        real_dump(obj, fp, indent=2, ensure_ascii=False)
        fp.flush()
        fp.write("GARBAGE")
        raise OSError("disk full during manifest write")
    monkeypatch.setattr(engine.json, "dump", exploding_dump)
    with pytest.raises(OSError):
        engine.save_manifest({"applied": [], "history": [], "rollbacks": []})
    after = (box / "patch_manifest.json").read_text(encoding="utf-8")
    assert after == before
    assert not (box / "patch_manifest.json.tmp").exists()


def test_B27_partial_backup_aborts_apply(box, monkeypatch):
    real_copy2 = __import__("shutil").copy2
    counter = {"i": 0}
    def failing_copy2(src, dst, *a, **kw):
        counter["i"] += 1
        if counter["i"] == 2:
            raise OSError("3rd-party interference")
        return real_copy2(src, dst, *a, **kw)
    monkeypatch.setattr(engine.shutil, "copy2", failing_copy2)
    put(box, "a.py", "x = 1\n")
    res = engine.apply_patch({"patch_id": "B27", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})
    assert res["success"] is False
    assert read(box / "a.py") == "x = 1\n"


def test_B28_safe_path_rejects_windows_seps_drive_and_empty():
    assert engine.safe_path("..\\..\\evil.py") is None
    assert engine.safe_path("sub\\evil.py") is None
    assert engine.safe_path("C:/evil.py") is None
    assert engine.safe_path("C:\\evil.py") is None
    assert engine.safe_path("") is None
    assert engine.safe_path(None) is None
    assert engine.safe_path("normal.py") == __import__("os").path.normpath(__import__("os").path.join(engine.BASE, "normal.py"))
    assert engine.safe_path("src/App.tsx") is not None


def test_B29_safe_path_symlink_escape(box, tmp_path):
    outside = box.parent / "outside29"
    outside.mkdir(exist_ok=True)
    link = box / "leak"
    try:
        os = __import__("os")
        os.symlink(str(outside), str(link))
    except (OSError, AttributeError):
        pytest.skip("symlink unavailable")
    assert engine.safe_path("leak/pwned.py") is None
    _, _, _, err = engine.compute_new({"type": "create", "target_file": "leak/pwned.py", "full_file_content": "p = 1\n"})
    assert err is not None
    assert not (outside / "pwned.py").exists()


# ---------- B32-B36: волна 2 — глубина отката и целостность транзакций ----------

def test_B32_rollback_chain_restores_each_step(box):
    put(box, "a.py", "x = 1\n")
    states = ["x = 1\n", "x = 2\n", "x = 3\n", "x = 4\n"]
    for i in (2, 3, 4):
        assert engine.apply_patch({"patch_id": f"B32-{i}", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": f"x = {i}\n"}
        ]})["success"]
    for expected in ("x = 3\n", "x = 2\n", "x = 1\n"):
        assert engine.rollback()["success"]
        assert read(box / "a.py") == expected
    res = engine.rollback()
    assert res["success"] is False


def test_B33_rollback_removes_created_but_restores_modified(box):
    put(box, "old.py", "y = 1\n")
    assert engine.apply_patch({"patch_id": "B33-MIX", "operations": [
        {"type": "create", "target_file": "new.py", "full_file_content": "n = 1\n"},
        {"type": "full_replace", "target_file": "old.py", "full_file_content": "y = 2\n"},
    ]})["success"]
    assert (box / "new.py").exists()
    assert read(box / "old.py") == "y = 2\n"
    assert engine.rollback()["success"]
    assert not (box / "new.py").exists()
    assert read(box / "old.py") == "y = 1\n"


def test_B34_rollback_missing_backup_fails_cleanly(box):
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch({"patch_id": "B34", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    man = engine.load_manifest()
    backup_path = engine._backup_path(man["applied"][-1]["operations"][-1]["backups"][0])
    os_import = __import__("os")
    os_import.remove(backup_path)
    res = engine.rollback()
    assert res["success"] is False
    assert read(box / "a.py") == "x = 2\n"
    after = engine.load_manifest()
    assert len(after["applied"]) == 1


def test_B35_rollback_legacy_manifest_entry(box):
    import json as _json
    put(box, "a.py", "y = 2\n")
    legacy_backup = (box / "backups" / "a.py_LATEST.bak")
    legacy_backup.write_text("y = 1\n", encoding="utf-8")
    legacy_entry = {"patch_id": "B35-LEGACY", "target_file": "a.py",
                    "applied_at": "2026-11-23T00:00:00", "checksum": "x",
                    "backups": [str(legacy_backup)]}
    engine.save_manifest({"applied": [legacy_entry], "history": [], "rollbacks": []})
    res = engine.rollback()
    assert res["success"]
    assert read(box / "a.py") == "y = 1\n"
    man = engine.load_manifest()
    assert len(man["applied"]) == 0 and len(man["rollbacks"]) == 1


def test_B36_manifest_cap_trimming_keeps_last_working(box):
    put(box, "a.py", "x = 1\n")
    for i in range(2, 104):
        assert engine.apply_patch({"patch_id": f"B36-{i}", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": f"x = {i}\n"}
        ]})["success"]
    man = engine.load_manifest()
    assert len(man["applied"]) == 100
    assert man["applied"][-1]["patch_id"] == "B36-103"
    assert engine.rollback()["success"]
    assert read(box / "a.py") == "x = 102\n"


# ---------- B40-B44: волна 3 — тампер-детект, дубликаты, строгий diff ----------

def test_B40_tampered_backup_detected_on_rollback(box):
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch({"patch_id": "B40", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    man = engine.load_manifest()
    backup_path = engine._backup_path(man["applied"][-1]["operations"][0]["backups"][0])
    with open(backup_path, "wb") as f:
        f.write(b"TAMPERED\n")
    res = engine.rollback()
    assert res["success"] is False
    assert "контрольной суммой" in res["error"]
    assert read(box / "a.py") == "x = 2\n"
    assert len(engine.load_manifest()["applied"]) == 1


def test_B40b_intact_backup_rollback_with_sha_still_works(box):
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch({"patch_id": "B40b", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    assert engine.rollback()["success"]
    assert read(box / "a.py") == "x = 1\n"


def test_B43_duplicate_patch_id_rejected(box):
    payload = {"patch_id": "B43-DUP", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]}
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch(payload)["success"]
    res = engine.apply_patch(payload)
    assert res["success"] is False
    assert "уже применён" in res["error"]
    assert read(box / "a.py") == "x = 2\n"
    assert len(engine.load_manifest()["applied"]) == 1


def test_B43b_reapply_after_rollback_allowed(box):
    payload = {"patch_id": "B43b", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]}
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch(payload)["success"]
    assert engine.rollback()["success"]
    assert engine.apply_patch(payload)["success"]
    assert read(box / "a.py") == "x = 2\n"


def test_B44_apply_diff_rejects_garbage():
    corpus = {
        "": "ни одного валидного ханка",
        "not a diff at all": "ни одного валидного ханка",
        "@@ garbage @@": "ни одного валидного ханка",
        "@@ -1,1 +1,1 @@" : "Пустой ханк",
        "@@ -1,1 +1,1 @@\n": "Пустой ханк",
    }
    for diff, expected in corpus.items():
        with pytest.raises(ValueError) as ei:
            engine.apply_diff("line1\nline2\n", diff)
        assert expected in str(ei.value), f"diff={diff!r}: {ei.value}"


# ---------- B45-B47: P0-исправления сервера (MD-guard, CRIT для bulk, SSRF-gate) ----------

def test_B45_api_md_refuses_non_md(box):
    (box / 'settings.json').write_text('{"v": 1}', encoding='utf-8')
    for target in ('settings.json', 'main.py', 'patch_engine.py', 'agents.json'):
        res = rsys.s_md_post(target, {'content': 'pwned'})
        data = json.loads(res.body)
        assert data['success'] is False, target
    assert json.loads((box / 'settings.json').read_text(encoding='utf-8')) == {'v': 1}
    assert not (box / 'main.py').exists()
    assert not (box / 'agents.json').exists()


def test_B45b_api_md_guard_allows_only_doc_md():
    assert guards.is_doc_rel('README.md')
    assert guards.is_doc_rel('RELEASE_NOTES.MD')
    assert guards.is_doc_rel('docs/ARCHITECTURE.md')
    assert not guards.is_doc_rel('notes.md.bak')
    assert not guards.is_doc_rel('src/readme.md')
    assert not guards.is_doc_rel('docs/../main.md')
    assert not guards.is_doc_rel('')
    assert not guards.is_doc_rel(None)


def test_B45c_api_md_get_refuses_non_md():
    data = json.loads(rsys.s_md_get('settings.json').body)
    assert data['content'] == '' and data['error']


def test_B45d_api_md_post_still_writes_doc_md(box):
    res = rsys.s_md_post('NEW.md', {'content': '# привет'})
    assert json.loads(res.body)['success'] is True
    assert (box / 'NEW.md').read_text(encoding='utf-8') == '# привет'


def test_B46_is_critical_rel_case_insensitive():
    assert guards.is_critical_rel('MAIN.PY')
    assert guards.is_critical_rel('settings.JSON')
    assert guards.is_critical_rel('SRC/app.py')
    assert guards.is_critical_rel('src\\app.tsx')
    assert guards.is_critical_rel('tests/test_engine.py')
    assert not guards.is_critical_rel('notes.txt')
    assert not guards.is_critical_rel('')
    assert not guards.is_critical_rel(None)


def test_B46_bulk_delete_respects_critical_files(box):
    put(box, 'settings.json', '{}')
    put(box, 'src/core.py', 'x = 1')
    put(box, 'notes.txt', 'x')
    res = rp.s_project_bulk({'action': 'delete', 'paths': ['settings.json', 'src/core.py', 'notes.txt']})
    data = json.loads(res.body)
    assert data['processed'] == 1
    assert data['skipped'] == 2
    assert (box / 'settings.json').exists()
    assert (box / 'src' / 'core.py').exists()
    assert not (box / 'notes.txt').exists()


def test_B46_bulk_delete_requires_backup(box, monkeypatch):
    monkeypatch.setattr(rp, 'backup', lambda p: [])
    put(box, 'notes.txt', 'x')
    data = json.loads(rp.s_project_bulk({'action': 'delete', 'paths': ['notes.txt']}).body)
    assert data['processed'] == 0 and data['skipped'] == 1
    assert (box / 'notes.txt').exists()


def test_B46_bulk_archive_requires_backup(box, monkeypatch):
    monkeypatch.setattr(rp, 'backup', lambda p: [])
    put(box, 'notes.txt', 'x')
    data = json.loads(rp.s_project_bulk({'action': 'archive', 'paths': ['notes.txt']}).body)
    assert data['processed'] == 0 and data['skipped'] == 1
    assert (box / 'notes.txt').exists()


def test_B46_bulk_archive_respects_critical_files(box):
    put(box, 'settings.json', '{}')
    data = json.loads(rp.s_project_bulk({'action': 'archive', 'paths': ['settings.json']}).body)
    assert data['processed'] == 0 and data['skipped'] == 1
    assert (box / 'settings.json').exists()


def test_B46_single_delete_requires_backup(box, monkeypatch):
    monkeypatch.setattr(rp, 'backup', lambda p: ())
    put(box, 'notes.txt', 'x')
    res = rp.s_proj_del({'path': 'notes.txt'})
    data = json.loads(res.body)
    assert data['success'] is False and 'резервную копию' in data['error']
    assert (box / 'notes.txt').exists()


def test_B46_single_delete_blocks_critical(box):
    put(box, 'main.py', 'x = 1')
    put(box, 'MAIN.PY', 'x = 1')
    assert json.loads(rp.s_proj_del({'path': 'main.py'}).body)['success'] is False
    assert json.loads(rp.s_proj_del({'path': 'MAIN.PY'}).body)['success'] is False
    assert (box / 'main.py').exists()


def test_B47_url_guard_rejects_metadata_and_garbage():
    assert guards.validate_url('ftp://example.com/x')[0] is False
    assert guards.validate_url('http://')[0] is False
    assert guards.validate_url('')[0] is False
    assert guards.validate_url(None)[0] is False
    assert guards.validate_url('http://user:pw@localhost:11434')[0] is False
    ok, why = guards.validate_url('http://169.254.169.254/latest/meta-data')
    assert not ok and 'link-local' in why.lower()
    ok, why = guards.validate_url('http://[fe80::1]/')
    assert not ok and 'link-local' in why.lower()
    ok, why = guards.validate_url('http://224.0.0.1/x')
    assert not ok and 'зарезервированный' in why
    assert guards.validate_url('http://10.0.0.5:8080', allowed_hosts={'api.groq.com'})[0] is False
    assert guards.validate_url('http://evil.example.com/v1', allowed_hosts={'api.groq.com'})[0] is False


def test_B47_url_guard_allows_legit():
    assert guards.validate_url('http://localhost:11434')[0]
    assert guards.validate_url('http://127.0.0.1:11434/api')[0]
    assert guards.validate_url('http://192.168.1.20:1234/v1')[0]
    assert guards.validate_url('http://10.1.2.3')[0]
    assert guards.validate_url('http://8.8.8.8')[0]


def test_B47_ping_blocks_metadata_url():
    st = json.loads(rprov.s_providers_ping({'providers': [{'id': 'ollama', 'url': 'http://169.254.169.254'}]}).body)['statuses']['ollama']
    assert st['online'] is False and 'отклонён' in st['error']


# ---------- B48-B52: P1-волна — целостность откатов, crash-журнал, блокировка манифеста ----------


def test_B48_rollback_refuses_user_edits_after_apply(box):
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch({"patch_id": "B48", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
    ]})["success"]
    (box / "a.py").write_bytes(b"x = USER_EDIT\n")
    res = engine.rollback()
    assert res["success"] is False
    assert "изменён после применения" in res["error"]
    assert read(box / "a.py") == "x = USER_EDIT\n"
    assert [a["patch_id"] for a in engine.load_manifest()["applied"]] == ["B48"]
    (box / "a.py").write_bytes(b"x = 2\n")
    res = engine.rollback()
    assert res["success"] is True
    assert read(box / "a.py") == "x = 1\n"


def test_B48b_rollback_refuses_deleted_file(box):
    put(box, "a.py", "x = 1\n")
    assert engine.apply_patch({"patch_id": "B48b", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
    ]})["success"]
    (box / "a.py").unlink()
    res = engine.rollback()
    assert res["success"] is False
    assert "исчез" in res["error"]
    assert [a["patch_id"] for a in engine.load_manifest()["applied"]] == ["B48b"]


def test_B49_rollback_staging_interrupted_then_resumes(box, monkeypatch):
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    assert engine.apply_patch({"patch_id": "B49", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})["success"]
    real_copy2 = engine.shutil.copy2
    mp = pytest.MonkeyPatch()

    def flaky_copy2(src, dst, *a, **kw):
        if str(dst).endswith(".rbk.tmp") and "b.py" in str(dst):
            raise OSError("3rd-party interference at staging")
        return real_copy2(src, dst, *a, **kw)

    mp.setattr(engine.shutil, "copy2", flaky_copy2)
    res = engine.rollback()
    mp.undo()
    assert res["success"] is False
    assert res["interrupted"] is True
    assert read(box / "a.py") == "x = 2\n"
    assert read(box / "b.py") == "y = 2\n"
    assert (box / "patch_journal.json").exists()
    res = engine.rollback()
    assert res["success"] is True
    assert read(box / "a.py") == "x = 1\n"
    assert read(box / "b.py") == "y = 1\n"
    assert engine.load_manifest()["applied"] == []
    assert engine.load_manifest()["rollbacks"][0]["patch_id"] == "B49"
    assert not (box / "patch_journal.json").exists()


def test_B50_partial_rollback_reported_not_hidden(box, monkeypatch):
    real_replace = engine.os.replace
    real_copy2 = engine.shutil.copy2

    def flaky_replace(src, dst, *a, **kw):
        if os.path.basename(str(dst)) == "b.py":
            raise OSError(28, "No space left on device")
        return real_replace(src, dst, *a, **kw)

    calls = {"n": 0}

    def counting_copy2(src, dst, *a, **kw):
        calls["n"] += 1
        if calls["n"] > 4:
            raise OSError("copy interfered during rollback")
        return real_copy2(src, dst, *a, **kw)

    mp = pytest.MonkeyPatch()
    mp.setattr(engine.os, "replace", flaky_replace)
    mp.setattr(engine.shutil, "copy2", counting_copy2)
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    res = engine.apply_patch({"patch_id": "B50", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})
    mp.undo()
    assert res["success"] is False
    assert res["rollback_incomplete"] is True
    assert "неполный" in res["error"] and "a.py" in res["error"]
    assert res["rollback_failed"]
    assert read(box / "a.py") == "x = 2\n"
    assert read(box / "b.py") == "y = 1\n"
    assert [a["patch_id"] for a in engine.load_manifest()["applied"]] == []


def test_B51_crash_journal_recovers_apply(box, monkeypatch):
    real_replace = engine.os.replace

    def flaky_replace(src, dst, *a, **kw):
        if os.path.basename(str(dst)) == "b.py":
            raise KeyboardInterrupt
        return real_replace(src, dst, *a, **kw)

    mp = pytest.MonkeyPatch()
    mp.setattr(engine.os, "replace", flaky_replace)
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    with pytest.raises(KeyboardInterrupt):
        engine.apply_patch({"patch_id": "B51", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
            {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
        ]})
    mp.undo()
    assert read(box / "a.py") == "x = 2\n"
    assert read(box / "b.py") == "y = 1\n"
    assert [a["patch_id"] for a in engine.load_manifest()["applied"]] == []
    assert (box / "patch_journal.json").exists()
    rec = engine.recover_journal()
    assert rec["action"] == "apply-reverted"
    assert read(box / "a.py") == "x = 1\n"
    assert read(box / "b.py") == "y = 1\n"
    assert not (box / "patch_journal.json").exists()
    assert engine.apply_patch({"patch_id": "B51", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})["success"]
    assert not (box / "patch_journal.json").exists()


def test_B52_corrupt_manifest_blocks_engine_until_reset(box):
    (box / "patch_manifest.json").write_text('{"applied": [ BROKEN', encoding="utf-8")
    put(box, "c.py", "z = 0\n")
    try:
        res = engine.apply_patch({"patch_id": "B52", "operations": [
            {"type": "full_replace", "target_file": "c.py", "full_file_content": "z = 1\n"},
        ]})
        assert res["success"] is False
        assert "поврежд" in res["error"]
        assert (box / "patch_manifest.json.corrupt").exists()
        assert read(box / "c.py") == "z = 0\n"
        assert engine.rollback()["success"] is False
        assert engine.stats()["locked"] is True
        res = engine.force_unlock_manifest()
        assert res["success"] is True
        assert engine.stats()["locked"] is False
    finally:
        engine.MANIFEST_LOCK = ""
    assert engine.apply_patch({"patch_id": "B52", "operations": [
        {"type": "full_replace", "target_file": "c.py", "full_file_content": "z = 1\n"},
    ]})["success"]
    assert read(box / "c.py") == "z = 1\n"
    assert [a["patch_id"] for a in engine.load_manifest()["applied"]] == ["B52"]

# ---------- B53-B60: P1/P2-волна 2 — персистентная история, снапшот important, структурный архив, providers/ollama, structured errors ----------


def test_B53_history_survives_restart(box, monkeypatch):
    put(box, "notes.txt", "x")
    res = json.loads(rp.s_project_bulk({"action": "delete", "paths": ["notes.txt"]}).body)
    assert res["success"] is True and res["processed"] == 1
    assert not (box / "notes.txt").exists()
    assert (box / ".project-history.json").exists()
    monkeypatch.setattr(rp, "PROJECT_HISTORY", rp._load_project_history())
    data = json.loads(rp.s_project_rollback().body)
    assert data["success"] is True
    assert "delete" in data["message"]
    assert read(box / "notes.txt") == "x"


def test_B54_rollback_important_restores_state(box, monkeypatch):
    put(box, "notes.txt", "x")
    res = json.loads(rp.s_project_bulk({"action": "important", "paths": ["notes.txt"]}).body)
    assert res["processed"] == 1
    assert "notes.txt" in rp.load_important()
    monkeypatch.setattr(rp, "PROJECT_HISTORY", rp._load_project_history())
    data = json.loads(rp.s_project_rollback().body)
    assert data["success"] is True
    assert "important" in data["message"]
    assert "notes.txt" not in rp.load_important()


def test_B55_archive_preserves_relative_path(box, monkeypatch):
    monkeypatch.setattr(engine, "BASE", str(box))
    put(box, "libs/utils/data.json", '{"a": 1}')
    put(box, "samples/data.json", '{"b": 2}')
    data = json.loads(rp.s_project_bulk({"action": "archive", "paths": ["libs/utils/data.json", "samples/data.json"]}).body)
    assert data["processed"] == 2
    assert len(data["archive"]) == 2
    assert not (box / "libs" / "utils" / "data.json").exists()
    stored = set()
    for orig, archived in data["archive"].items():
        assert archived.endswith(orig)
        assert (box / archived).exists()
        stored.add(archived)
    assert len(stored) == 2
    assert not (box / "data.json").exists()
    for orig, archived in data["archive"].items():
        res = json.loads(rp.s_project_restore({"archive_path": archived}).body)
        assert res["success"] is True
    assert read(box / "libs" / "utils" / "data.json") == '{"a": 1}'
    assert read(box / "samples" / "data.json") == '{"b": 2}'


def test_B55_archive_collision_same_filename(box):
    put(box, "libs/a/data.txt", "1")
    put(box, "samples/b/data.txt", "2")
    data = json.loads(rp.s_project_bulk({"action": "archive", "paths": ["libs/a/data.txt", "samples/b/data.txt"]}).body)
    assert data["processed"] == 2
    p1 = data["archive"]["libs/a/data.txt"]
    p2 = data["archive"]["samples/b/data.txt"]
    assert p1 != p2
    p1 = data["archive"]["libs/a/data.txt"]
    p2 = data["archive"]["samples/b/data.txt"]


def test_B55_restore_rejects_non_archive_and_critical(box):
    res = json.loads(rp.s_project_restore({"archive_path": "notes.txt"}).body)
    assert res["success"] is False
    put(box, "settings.json", "{}")
    dst = box / "project_archive" / "stamp" / "settings.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("{}")
    res = json.loads(rp.s_project_restore({"archive_path": "project_archive/stamp/settings.json"}).body)
    assert res["success"] is False and "критичн" in res["error"]


def test_B56_providers_config_writes_settings_and_rebuilds_engine(box, monkeypatch):
    monkeypatch.setattr(rprov, "CONFIG", str(box / "settings.json"))
    monkeypatch.setattr(shared, "CONFIG", str(box / "settings.json"))
    shared.engine_obj = {"stub": True}
    try:
        res = json.loads(rprov.s_providers_config({"config": {"groq_api_key": "k-123"}}).body)
        assert res["success"] is True and res["file"] == "settings.json"
        assert json.loads((box / "settings.json").read_text(encoding="utf-8"))["groq_api_key"] == "k-123"
        assert not isinstance(shared.engine_obj, dict)
        assert getattr(shared.engine_obj, "config", {}).get("groq_api_key") == "k-123"
    finally:
        shared.engine_obj = None


def test_B57_ollama_client_uses_configured_host():
    e = agent_engine.AgentEngine({"ollama_url": "http://127.0.0.1:11437"}, log_callback=lambda *a, **kw: None)
    assert str(e._ollama._client.base_url).rstrip("/") == "http://127.0.0.1:11437"
    seen = {}

    def fake_chat(model, messages, **kw):
        seen["model"] = model
        return {"message": {"content": "ok"}}

    e._ollama.chat = fake_chat
    assert asyncio.run(e._query_ollama("m1", [])) == "ok"
    assert seen["model"] == "m1"


def test_B58_candidates_include_local_providers():
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    provs = {c["provider"] for c in e._get_candidates()}
    assert {"bionic", "lmstudio", "strata"} <= provs


def collect(agen):
    async def run():
        out = []
        async for ev in agen:
            out.append(ev)
        return out
    return asyncio.run(run())


def test_B58_stream_all_fails_over_to_next(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    monkeycands = [{"provider": "ollama", "model": "m1", "name": "m1"},
                   {"provider": "ollama", "model": "m2", "name": "m2"}]
    e._get_candidates = lambda: monkeycands

    def fake_chat(model, messages, stream=False, **kw):
        if model == "m1":
            raise ConnectionError("refused")
        assert stream is True
        return iter([{"message": {"content": "ok"}}])

    e._ollama.chat = fake_chat
    evs = collect(e.stream_task("hi", provider="all"))
    kinds = [x["type"] for x in evs]
    assert "chunk" in kinds
    fo = [x for x in evs if x["type"] == "failover"]
    assert fo and fo[0]["provider"] == "ollama" and fo[0]["model"] == "m1" and fo[0]["next"] is True
    assert "".join(x["content"] for x in evs if x["type"] == "chunk") == "ok"
    assert kinds[-1] == "done" and evs[-1]["model"] == "m2"
    assert "error" not in kinds


def test_B58_stream_all_reports_error_when_chain_exhausted(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    monkeycands = [{"provider": "ollama", "model": "m1", "name": "m1"},
                   {"provider": "ollama", "model": "m2", "name": "m2"}]
    e._get_candidates = lambda: monkeycands

    def fake_chat(model, messages, stream=False, **kw):
        raise ConnectionError("down")

    e._ollama.chat = fake_chat
    evs = collect(e.stream_task("hi", provider="all"))
    errors = [x for x in evs if x["type"] == "error"]
    assert len(errors) == 1
    assert errors[0]["providers"] == ["ollama", "ollama"]
    assert errors[0]["details"][0]["model"] == "m1"


def test_B60_run_task_structured_error(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)

    def fake_chat(model, messages, **kw):
        raise ConnectionError("down")

    e._ollama.chat = fake_chat
    res = asyncio.run(e.run_task("hi", mode="fast", provider="ollama", model="m1"))
    assert isinstance(res, dict)
    assert res["success"] is False
    assert res["result"] == ""
    assert res["providers"] == ["ollama"]
    assert "All models failed" in res["error"]


def test_B60_run_task_successful_result_structured(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)

    def fake_chat(model, messages, **kw):
        return {"message": {"content": "x = 1\n"}}

    e._ollama.chat = fake_chat
    res = asyncio.run(e.run_task("hi", mode="fast", provider="ollama", model="m1"))
    assert res["success"] is True
    assert res["result"] == "x = 1\n"



# ========================= ВОЛНА 3: B61–B72 (P2-14 … P3-25) =========================

B72T = "from version import VERSION"


def test_B61_backup_two_copies_and_no_verified(box):
    p = put(box, "a.py", "x = 1\n")
    for _ in range(3):
        backs = engine.backup(str(p))
        assert len(backs) == 2
        assert not any("_verified" in os.path.basename(b) for b in backs)
        assert any(os.path.basename(b).endswith("_LATEST.bak") for b in backs)


def test_B61_backup_names_remain_unique_when_clock_repeats(box, monkeypatch):
    from datetime import datetime as RealDateTime

    p = put(box, "same-clock.py", "x = 1\n")

    class FrozenDateTime:
        @classmethod
        def now(cls):
            return RealDateTime(2026, 11, 26, 12, 0, 0, 123456)

    monkeypatch.setattr(engine, "datetime", FrozenDateTime)
    paths = [engine.backup(str(p))[0] for _ in range(3)]
    assert all(paths)
    assert len(set(paths)) == 3
    assert all(os.path.isfile(path) for path in paths)


def test_B61_backup_rotation_keep10(box):
    p = put(box, "b.py", "y = 1\n")
    for _ in range(14):
        engine.backup(str(p))
    name = "b.py"
    stamps = [f for f in os.listdir(engine.BACKUP_DIR)
              if f.startswith(name + "_") and f.endswith(".bak") and not f.endswith("_LATEST.bak")]
    assert len(stamps) == 10
    latest = [f for f in os.listdir(engine.BACKUP_DIR) if f.endswith("_LATEST.bak")]
    assert len(latest) == 1


def test_B69_manifest_backup_paths_relative(box):
    put(box, "a.py", "x = 1\n")
    r = engine.apply_patch({"patch_id": "B69", "operations": [
        {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
    ]})
    assert r["success"]
    raw = open(engine.MANIFEST, "r", encoding="utf-8").read()
    assert str(box) not in raw
    entry = engine.load_manifest()["applied"][-1]
    for b in entry["backups"]:
        assert not os.path.isabs(b)
        assert b.replace("\\", "/").startswith("backups/")
    assert all(os.path.exists(engine._backup_path(b)) for b in entry["backups"])


def test_B69_rollback_with_relative_paths(box):
    put(box, "a.py", "x = 1\n")
    r = engine.apply_patch({"patch_id": "B69r", "operations": [
        {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
    ]})
    assert r["success"]
    rr = engine.rollback()
    assert rr["success"], rr
    assert read(box / "a.py") == "x = 1\n"


def test_B69_rollback_accepts_legacy_absolute_backup_paths(box):
    put(box, "a.py", "x = 1\n")
    r = engine.apply_patch({"patch_id": "B69l", "operations": [
        {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
    ]})
    assert r["success"]
    man = engine.load_manifest()
    entry = man["applied"][-1]
    for op in entry["operations"]:
        op["backups"] = [os.path.join(str(box), p.replace("/", os.sep)) if not os.path.isabs(p) else p
                         for p in op["backups"]]
    entry["backups"] = [os.path.join(str(box), p.replace("/", os.sep)) if not os.path.isabs(p) else p
                        for p in entry["backups"]]
    engine.save_manifest(man)
    rr = engine.rollback()
    assert rr["success"], rr
    assert read(box / "a.py") == "x = 1\n"


class _FakeR:
    def __init__(self, code, out="", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def test_B62_ts_types_error_blocks_apply(box, monkeypatch):
    (box / "tools").mkdir()
    (box / "tools" / "tscheck.cjs").write_text("// dummy", encoding="utf-8")
    monkeypatch.setattr(engine, "_tsc_cmd", lambda: ["fake-tsc"])
    monkeypatch.setattr(engine, "check_ts", lambda *a, **k: None)
    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: _FakeR(1, "TS2322: type mismatch"))
    put(box, "src/c.ts", "const a: number = 1;\n")
    res = engine.apply_patch({"patch_id": "B62bad", "operations": [
        {"type": "search_and_replace", "target_file": "src/c.ts", "find": "1", "replace": "2"},
    ]})
    assert res["success"] is False
    assert "tsc --noEmit" in res["error"]
    assert read(box / "src" / "c.ts") == "const a: number = 1;\n"
    assert engine.load_manifest()["applied"] == []


def test_B62_ts_types_ok_patch_applies(box, monkeypatch):
    (box / "tools").mkdir()
    (box / "tools" / "tscheck.cjs").write_text("// dummy", encoding="utf-8")
    monkeypatch.setattr(engine, "_tsc_cmd", lambda: ["fake-tsc"])
    monkeypatch.setattr(engine, "check_ts", lambda *a, **k: None)
    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: _FakeR(0, ""))
    put(box, "src/c.ts", "const a: number = 1;\n")
    res = engine.apply_patch({"patch_id": "B62ok", "operations": [
        {"type": "search_and_replace", "target_file": "src/c.ts", "find": "1", "replace": "2"},
    ]})
    assert res["success"], res
    assert read(box / "src" / "c.ts") == "const a: number = 2;\n"


def test_B62_tsc_unavailable_skips_full_check(box, monkeypatch):
    (box / "tools").mkdir()
    (box / "tools" / "tscheck.cjs").write_text("// dummy", encoding="utf-8")
    monkeypatch.setattr(engine, "_tsc_cmd", lambda: None)
    monkeypatch.setattr(engine, "check_ts", lambda *a, **k: None)
    put(box, "src/c.tsx", "const A = () => { return <b>x</b>; };\n")
    res = engine.apply_patch({"patch_id": "B62skip", "operations": [
        {"type": "search_and_replace", "target_file": "src/c.tsx", "find": "x", "replace": "y"},
    ]})
    assert res["success"], res
    assert read(box / "src" / "c.tsx") == "const A = () => { return <b>y</b>; };\n"


def test_B62_check_ts_full_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(engine, "_tsc_cmd", lambda: None)
    assert engine.check_ts_full() is None


def test_B63_apply_all_honest_success(box):
    (box / "patch" / "B63P.json").write_text(json.dumps({
        "patch_id": "B63P",
        "operations": [
            {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
        ],
    }), encoding="utf-8")
    put(box, "a.py", "z = 0\n")
    body = json.loads(rpat.s_pall({}).body)
    assert body["success"] is False
    assert body["results"][0]["success"] is False
    assert read(box / "a.py") == "z = 0\n"


def test_B63_apply_all_success_when_all_good(box):
    (box / "patch" / "B63G.json").write_text(json.dumps({
        "patch_id": "B63G",
        "operations": [
            {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
        ],
    }), encoding="utf-8")
    put(box, "a.py", "x = 1\n")
    body = json.loads(rpat.s_pall({}).body)
    assert body["success"] is True
    assert body["results"][0]["success"] is True
    assert read(box / "a.py") == "x = 2\n"


def test_B64_validate_all_uses_safe_path(box, monkeypatch):
    monkeypatch.setattr(engine, "PATCH_DIR", str(box / "patch"))
    monkeypatch.setattr(rpat, "PATCH_DIR", str(box / "patch"))
    (box / "patch" / "B64evil.json").write_text(json.dumps({
        "patch_id": "B64evil",
        "operations": [
            {"type": "search_and_replace", "target_file": "../outside.txt", "find": "a", "replace": "b"},
        ],
    }), encoding="utf-8")
    (tmp_out := box.parent / "outside.txt").write_text("a\n", encoding="utf-8")
    res = rpat.s_pvalidate_all()
    body = json.loads(res.body)
    entry = [x for x in body["patches"] if x["filename"] == "B64evil.json"][0]
    assert any("подозрительный target_file" in e for e in entry["errors"])


def test_B72_apply_py_sets_restart_flag(box, monkeypatch):
    monkeypatch.setattr(rpat, "RESTART_FLAG", str(box / "restart.flag"))
    put(box, "a.py", "x = 1\n")
    body = json.loads(rpat.s_papply({"patch_id": "B72py", "operations": [
        {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
    ]}).body)
    assert body["success"] is True
    assert body.get("restart_scheduled") is True
    assert (box / "restart.flag").exists()


def test_B72_apply_nonpy_sets_no_restart_flag(box, monkeypatch):
    monkeypatch.setattr(rpat, "RESTART_FLAG", str(box / "restart.flag"))
    put(box, "conf.txt", "k = v\n")
    body = json.loads(rpat.s_papply({"patch_id": "B72txt", "operations": [
        {"type": "search_and_replace", "target_file": "conf.txt", "find": "k = v", "replace": "k = w"},
    ]}).body)
    assert body["success"] is True
    assert "restart_scheduled" not in body
    assert not (box / "restart.flag").exists()


def test_B68_version_single_source():
    version = importlib.import_module("version")
    pkg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "package.json"), encoding="utf-8"))
    assert pkg["version"] == version.VERSION
    assert engine.stats()["version"] == version.VERSION


def test_B68_shell_version_from_api():
    """Оболочка берёт версию из /api/version (version.py) — хардкод версии в Header.tsx запрещён."""
    import io as _io
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    header = _io.open(os.path.join(root, "src", "components", "layout", "Header.tsx"), encoding="utf-8").read()
    assert not re.search(r"v\.\d+\.\d+", header), "в Header.tsx захардкожена версия"
    assert "version" in header, "Header.tsx должен использовать проп version"
    app = _io.open(os.path.join(root, "src", "App.tsx"), encoding="utf-8").read()
    assert "loadAppVersionApi" in app and "version={appVersion}" in app
    api = _io.open(os.path.join(root, "src", "services", "api.ts"), encoding="utf-8").read()
    assert "/api/version" in api
    api_src = _io.open(os.path.join(root, "api", "routes_system.py"), encoding="utf-8").read()
    assert "/api/version" in api_src and "_VER" in api_src


# ========================= B59: Fast возвращает первое готовое ответ =========================

def test_B59_fast_returns_first_ready(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    slow_c = {"provider": "ollama", "model": "slow", "name": "ollama: slow"}
    fast_c = {"provider": "ollama", "model": "fast", "name": "ollama: fast"}
    e._get_candidates = lambda: [slow_c, fast_c]

    async def fake(c, prompt):
        if c["model"] == "slow":
            await asyncio.sleep(0.5)
            return {"code": "SLOW", "candidate": c}
        return {"code": "FAST", "candidate": c}

    e.get_code_response = fake
    res = asyncio.run(e.run_task("hi", mode="fast"))
    assert res["success"] is True
    assert res["result"] == "FAST"
    assert res["providers"] == ["ollama"]
    assert res["error"] is None


def test_B59_fast_all_fail_structured(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    c1 = {"provider": "ollama", "model": "m1", "name": "ollama: m1"}
    c2 = {"provider": "ollama", "model": "m2", "name": "ollama: m2"}
    e._get_candidates = lambda: [c1, c2]

    async def fake(c, prompt):
        raise ConnectionError("down")

    e.get_code_response = fake
    res = asyncio.run(e.run_task("hi", mode="fast"))
    assert res["success"] is False
    assert res["result"] == ""
    assert res["providers"] == ["ollama", "ollama"]


def test_B59_fast_skips_failed_and_takes_next_success(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    bad_c = {"provider": "ollama", "model": "bad", "name": "ollama: bad"}
    good_c = {"provider": "ollama", "model": "good", "name": "ollama: good"}
    e._get_candidates = lambda: [bad_c, good_c]

    async def fake(c, prompt):
        if c["model"] == "bad":
            return {"candidate": c, "error": "empty"}
        return {"code": "SECOND", "candidate": c}

    e.get_code_response = fake
    res = asyncio.run(e.run_task("hi", mode="fast"))
    assert res["success"] is True
    assert res["result"] == "SECOND"


def test_B59_fast_mode_does_not_wait_slow_models(box):
    e = agent_engine.AgentEngine({}, log_callback=lambda *a, **kw: None)
    slow_c = {"provider": "ollama", "model": "slow", "name": "ollama: slow"}
    fast_c = {"provider": "ollama", "model": "fast", "name": "ollama: fast"}
    e._get_candidates = lambda: [slow_c, fast_c]

    async def fake(c, prompt):
        if c["model"] == "slow":
            await asyncio.sleep(10)
            return {"code": "SLOW", "candidate": c}
        await asyncio.sleep(0.05)
        return {"code": "QUICK", "candidate": c}

    e.get_code_response = fake
    t0 = time.monotonic()
    res = asyncio.run(e.run_task("hi", mode="fast"))
    dt = time.monotonic() - t0
    assert res["success"] is True and res["result"] == "QUICK"
    assert dt < 5
