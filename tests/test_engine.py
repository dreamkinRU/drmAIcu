# tests/test_engine.py
import importlib
import json
import pytest

main = importlib.import_module("main")
import patch_engine as engine


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
    monkeypatch.setattr(main, "PROJ_ARCHIVE", str(base / "project_archive"))
    monkeypatch.setattr(engine, "MANIFEST", str(base / "patch_manifest.json"))
    monkeypatch.setattr(main, "IMPORTANT", str(base / ".project-important.json"))
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
    out = main.apply_search_replace("l1\r\nl2\r\nl3\r\n", "l2\n", "L2\n")
    assert out == "l1\r\nL2\r\nl3\r\n"


def test_OK_search_replace_ambiguous():
    with pytest.raises(ValueError):
        main.apply_search_replace("a\na\n", "a", "b")


def test_OK_diff_basic():
    assert main.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\n a\n-b\n+B") == "a\nB\nc"


def test_OK_diff_idempotent():
    d = "@@ -1,3 +1,3 @@\n a\n-b\n+B"
    once = main.apply_diff("a\nb\nc", d)
    assert main.apply_diff(once, d) == once


def test_OK_create_rejects_existing(box):
    put(box, "x.py", "a = 1\n")
    _, _, _, err = main.compute_new(
        {"type": "create", "target_file": "x.py", "full_file_content": "b = 2\n"}
    )
    assert err is not None


def test_OK_phase1_blocks_everything(box):
    put(box, "good.py", "a = 1\n")
    res = main.apply_patch({"patch_id": "T1", "operations": [
        {"type": "full_replace", "target_file": "good.py", "full_file_content": "a = 2\n"},
        {"type": "full_replace", "target_file": "bad.py", "full_file_content": "def f(:\n"},
    ]})
    assert res["success"] is False
    assert read(box / "good.py") == "a = 1\n"
    assert not (box / "bad.py").exists()


def test_OK_multi_apply_and_rollback(box):
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    assert main.apply_patch({"patch_id": "T2", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})["success"]
    assert main.rollback()["success"]
    assert read(box / "a.py") == "x = 1\n"
    assert read(box / "b.py") == "y = 1\n"


# ---------- БАГИ: должно ПАДАТЬ на текущем коде ----------

def test_BUG01_diff_trailing_newline():
    """B1: хвостовой \n превращается в фантомную пустую строку контекста."""
    assert main.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n") == "a\nB\nc"


def test_BUG02_diff_crlf_injection():
    """B2: apply_diff не нормализует CRLF -> \\r остаётся в файле."""
    out = main.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\r\n a\r\n-b\r\n+B")
    assert "\r" not in out


def test_BUG03_pure_insert_position():
    """B3: @@ -2,0 @@ = вставить ПОСЛЕ строки 2, а не до."""
    assert main.apply_diff("l1\nl2\nl3", "@@ -2,0 +3,1 @@\n+INSERTED") == "l1\nl2\nINSERTED\nl3"


def test_BUG04_silent_skip_unmatched_hunk():
    """B4: old не найден, new найден в другом месте -> молчаливый пропуск."""
    with pytest.raises(ValueError):
        main.apply_diff("x\na\nb", "@@ -2,2 +2,1 @@\n a\n-ZZZ")


def test_BUG05_silent_skip_pure_delete():
    """B5: пустой new_block -> find_block возвращает hint -> пропуск всегда."""
    with pytest.raises(ValueError):
        main.apply_diff("a\nb", "@@ -1,2 +1,0 @@\n-a\n-ZZZ")


def test_BUG06_backup_basename_collision(box):
    """B6: src/App.tsx и public/App.tsx пишутся в один и тот же .bak."""
    b1 = main.backup(str(put(box, "src/App.tsx", "SRC")))
    b2 = main.backup(str(put(box, "public/App.tsx", "PUB")))
    assert set(b1).isdisjoint(set(b2))


def test_BUG07_failed_file_not_rolled_back(box, monkeypatch):
    """B7: файл, не прошедший SHA-проверку, отсутствует в written -> не откатывается."""
    put(box, "a.py", "x = 1\n")
    put(box, "b.py", "y = 1\n")
    real, n = main.sha_bytes, {"i": 0}

    def fake(data):
        n["i"] += 1
        return "bogus" if n["i"] > 2 else real(data)

    monkeypatch.setattr(engine, "sha_bytes", fake)
    res = main.apply_patch({"patch_id": "T3", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
        {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
    ]})
    assert res["success"] is False
    assert read(box / "a.py") == "x = 1\n"


def test_BUG08_tsx_not_validated():
    """B8: сломанный TSX проходит валидацию."""
    ok, _ = main.validate("src/App.tsx", "const x = ((( ;")
    assert ok is False


def test_BUG09_path_escape(box):
    """B9: target_file выходит за пределы проекта."""
    _, _, _, err = main.compute_new(
        {"type": "create", "target_file": "../escaped.py", "full_file_content": "p = 1\n"}
    )
    assert err is not None


def test_BUG10_backups_marked_critical():
    """B10: backups/ в CRIT_DIRS -> очистка никогда их не удалит."""
    assert main.category("App.tsx_1.bak", "backups/App.tsx_1.bak", 100) == "backup"


def test_BUG11_newline_rewrite_on_windows(box):
    """B11: LF-файл перезаписывается как CRLF, SHA-проверка это не ловит."""
    put(box, "a.py", "x = 1\ny = 2\n")
    assert main.apply_patch({"patch_id": "T4", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 1\ny = 3\n"},
    ]})["success"]
    assert (box / "a.py").read_bytes() == b"x = 1\ny = 3\n"


def test_BUG18_multi_ops_same_file(box):
    """B18: two ops on one file must accumulate, not overwrite."""
    put(box, "a.py", "x = 1\ny = 1\n")
    res = main.apply_patch({"patch_id": "T5", "operations": [
        {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
        {"type": "search_and_replace", "target_file": "a.py", "find": "y = 1", "replace": "y = 2"},
    ]})
    assert res["success"]
    assert read(box / "a.py") == "x = 2\ny = 2\n"

# ---------- B20-B24: движок 3.6.0 (fix PATCHES) ----------

def test_BUG20_expected_sha_mismatch_rejected(box):
    """B20: expected_sha не совпал с содержимым на диске -> патч отвергнут целиком."""
    put(box, "a.py", "x = 1\n")
    res = main.apply_patch({"patch_id": "T-B20", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n",
         "expected_sha": "deadbeef"},
    ]})
    assert res["success"] is False
    assert "expected_sha" in res["error"]
    assert read(box / "a.py") == "x = 1\n"


def test_BUG20b_expected_sha_match_applies(box):
    """B20: корректный expected_sha пропускает патч."""
    put(box, "a.py", "x = 1\n")
    good = main.sha_bytes(b"x = 1\n")
    res = main.apply_patch({"patch_id": "T-B20b", "operations": [
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
        res = main.apply_patch({"patch_id": "T-B21", "operations": [
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
    main.save_manifest({'applied': [{'patch_id': 'EVIL', 'operations': [
        {'target_file': '../victim.txt', 'backups': []},
    ]}], 'history': [], 'rollbacks': []})
    res = main.rollback()
    assert res["success"] is False
    assert (box / "victim.txt").exists()


def test_BUG23_stats_endpoint_not_shadowed():
    """B23: /api/patches/stats файлов регистрируется ровно один раз, s_pstats жив."""
    stats_routes = [r for r in main.app.routes if getattr(r, 'path', '') == '/api/patches/stats']
    assert len(stats_routes) == 1
    handler = getattr(stats_routes[0], 'endpoint', None)
    assert handler is main.s_pstats


def test_BUG24_tx_lock_serializes_toggle():
    """B24: TX_LOCK существует и является RLock (apply/rollback сериализуются)."""
    got = []
    def hold_in_subthread():
        if main.TX_LOCK.acquire(timeout=2):
            got.append(True)
            import time; time.sleep(0.3)
            main.TX_LOCK.release()
    import threading as th
    t = th.Thread(target=hold_in_subthread)
    t.start()
    t.join(2)
    assert got == [True]
    assert main.TX_LOCK.acquire(timeout=2)
    main.TX_LOCK.release()


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
    res = main.apply_patch({"patch_id": "EVIL25", "filename": "../../evil.json"})
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
    res = main.apply_patch({"patch_id": "B25BODY"})
    assert res["success"]
    assert read(box / "a.py") == "x = 2\n"


def test_B26_manifest_write_crash_keeps_old_state(box, monkeypatch):
    import json as _json
    put(box, "a.py", "x = 1\n")
    assert main.apply_patch({"patch_id": "B26-SETUP", "operations": [
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
    res = main.apply_patch({"patch_id": "B27", "operations": [
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
    _, _, _, err = main.compute_new({"type": "create", "target_file": "leak/pwned.py", "full_file_content": "p = 1\n"})
    assert err is not None
    assert not (outside / "pwned.py").exists()


# ---------- B32-B36: волна 2 — глубина отката и целостность транзакций ----------

def test_B32_rollback_chain_restores_each_step(box):
    put(box, "a.py", "x = 1\n")
    states = ["x = 1\n", "x = 2\n", "x = 3\n", "x = 4\n"]
    for i in (2, 3, 4):
        assert main.apply_patch({"patch_id": f"B32-{i}", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": f"x = {i}\n"}
        ]})["success"]
    for expected in ("x = 3\n", "x = 2\n", "x = 1\n"):
        assert main.rollback()["success"]
        assert read(box / "a.py") == expected
    res = main.rollback()
    assert res["success"] is False


def test_B33_rollback_removes_created_but_restores_modified(box):
    put(box, "old.py", "y = 1\n")
    assert main.apply_patch({"patch_id": "B33-MIX", "operations": [
        {"type": "create", "target_file": "new.py", "full_file_content": "n = 1\n"},
        {"type": "full_replace", "target_file": "old.py", "full_file_content": "y = 2\n"},
    ]})["success"]
    assert (box / "new.py").exists()
    assert read(box / "old.py") == "y = 2\n"
    assert main.rollback()["success"]
    assert not (box / "new.py").exists()
    assert read(box / "old.py") == "y = 1\n"


def test_B34_rollback_missing_backup_fails_cleanly(box):
    put(box, "a.py", "x = 1\n")
    assert main.apply_patch({"patch_id": "B34", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    man = engine.load_manifest()
    backup_path = man["applied"][-1]["operations"][-1]["backups"][0]
    os_import = __import__("os")
    os_import.remove(backup_path)
    res = main.rollback()
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
    res = main.rollback()
    assert res["success"]
    assert read(box / "a.py") == "y = 1\n"
    man = engine.load_manifest()
    assert len(man["applied"]) == 0 and len(man["rollbacks"]) == 1


def test_B36_manifest_cap_trimming_keeps_last_working(box):
    put(box, "a.py", "x = 1\n")
    for i in range(2, 104):
        assert main.apply_patch({"patch_id": f"B36-{i}", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": f"x = {i}\n"}
        ]})["success"]
    man = engine.load_manifest()
    assert len(man["applied"]) == 100
    assert man["applied"][-1]["patch_id"] == "B36-103"
    assert main.rollback()["success"]
    assert read(box / "a.py") == "x = 102\n"


# ---------- B40-B44: волна 3 — тампер-детект, дубликаты, строгий diff ----------

def test_B40_tampered_backup_detected_on_rollback(box):
    put(box, "a.py", "x = 1\n")
    assert main.apply_patch({"patch_id": "B40", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    man = engine.load_manifest()
    backup_path = man["applied"][-1]["operations"][0]["backups"][0]
    with open(backup_path, "wb") as f:
        f.write(b"TAMPERED\n")
    res = main.rollback()
    assert res["success"] is False
    assert "контрольной суммой" in res["error"]
    assert read(box / "a.py") == "x = 2\n"
    assert len(engine.load_manifest()["applied"]) == 1


def test_B40b_intact_backup_rollback_with_sha_still_works(box):
    put(box, "a.py", "x = 1\n")
    assert main.apply_patch({"patch_id": "B40b", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]})["success"]
    assert main.rollback()["success"]
    assert read(box / "a.py") == "x = 1\n"


def test_B43_duplicate_patch_id_rejected(box):
    payload = {"patch_id": "B43-DUP", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]}
    put(box, "a.py", "x = 1\n")
    assert main.apply_patch(payload)["success"]
    res = main.apply_patch(payload)
    assert res["success"] is False
    assert "уже применён" in res["error"]
    assert read(box / "a.py") == "x = 2\n"
    assert len(engine.load_manifest()["applied"]) == 1


def test_B43b_reapply_after_rollback_allowed(box):
    payload = {"patch_id": "B43b", "operations": [
        {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
    ]}
    put(box, "a.py", "x = 1\n")
    assert main.apply_patch(payload)["success"]
    assert main.rollback()["success"]
    assert main.apply_patch(payload)["success"]
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
            main.apply_diff("line1\nline2\n", diff)
        assert expected in str(ei.value), f"diff={diff!r}: {ei.value}"


# ---------- B45-B47: P0-исправления сервера (MD-guard, CRIT для bulk, SSRF-gate) ----------

def test_B45_api_md_refuses_non_md(box):
    (box / 'settings.json').write_text('{"v": 1}', encoding='utf-8')
    for target in ('settings.json', 'main.py', 'patch_engine.py', 'agents.json'):
        res = main.s_md_post(target, {'content': 'pwned'})
        data = json.loads(res.body)
        assert data['success'] is False, target
    assert json.loads((box / 'settings.json').read_text(encoding='utf-8')) == {'v': 1}
    assert not (box / 'main.py').exists()
    assert not (box / 'agents.json').exists()


def test_B45b_api_md_guard_allows_only_doc_md():
    assert main.is_doc_rel('README.md')
    assert main.is_doc_rel('RELEASE_NOTES.MD')
    assert main.is_doc_rel('docs/ARCHITECTURE.md')
    assert not main.is_doc_rel('notes.md.bak')
    assert not main.is_doc_rel('src/readme.md')
    assert not main.is_doc_rel('docs/../main.md')
    assert not main.is_doc_rel('')
    assert not main.is_doc_rel(None)


def test_B45c_api_md_get_refuses_non_md():
    data = json.loads(main.s_md_get('settings.json').body)
    assert data['content'] == '' and data['error']


def test_B45d_api_md_post_still_writes_doc_md(box):
    res = main.s_md_post('NEW.md', {'content': '# привет'})
    assert json.loads(res.body)['success'] is True
    assert (box / 'NEW.md').read_text(encoding='utf-8') == '# привет'


def test_B46_is_critical_rel_case_insensitive():
    assert main.is_critical_rel('MAIN.PY')
    assert main.is_critical_rel('settings.JSON')
    assert main.is_critical_rel('SRC/app.py')
    assert main.is_critical_rel('src\\app.tsx')
    assert main.is_critical_rel('tests/test_engine.py')
    assert not main.is_critical_rel('notes.txt')
    assert not main.is_critical_rel('')
    assert not main.is_critical_rel(None)


def test_B46_bulk_delete_respects_critical_files(box):
    put(box, 'settings.json', '{}')
    put(box, 'src/core.py', 'x = 1')
    put(box, 'notes.txt', 'x')
    res = main.s_project_bulk({'action': 'delete', 'paths': ['settings.json', 'src/core.py', 'notes.txt']})
    data = json.loads(res.body)
    assert data['processed'] == 1
    assert data['skipped'] == 2
    assert (box / 'settings.json').exists()
    assert (box / 'src' / 'core.py').exists()
    assert not (box / 'notes.txt').exists()


def test_B46_bulk_delete_requires_backup(box, monkeypatch):
    monkeypatch.setattr(main, 'backup', lambda p: [])
    put(box, 'notes.txt', 'x')
    data = json.loads(main.s_project_bulk({'action': 'delete', 'paths': ['notes.txt']}).body)
    assert data['processed'] == 0 and data['skipped'] == 1
    assert (box / 'notes.txt').exists()


def test_B46_bulk_archive_requires_backup(box, monkeypatch):
    monkeypatch.setattr(main, 'backup', lambda p: [])
    put(box, 'notes.txt', 'x')
    data = json.loads(main.s_project_bulk({'action': 'archive', 'paths': ['notes.txt']}).body)
    assert data['processed'] == 0 and data['skipped'] == 1
    assert (box / 'notes.txt').exists()


def test_B46_bulk_archive_respects_critical_files(box):
    put(box, 'settings.json', '{}')
    data = json.loads(main.s_project_bulk({'action': 'archive', 'paths': ['settings.json']}).body)
    assert data['processed'] == 0 and data['skipped'] == 1
    assert (box / 'settings.json').exists()


def test_B46_single_delete_requires_backup(box, monkeypatch):
    monkeypatch.setattr(main, 'backup', lambda p: ())
    put(box, 'notes.txt', 'x')
    res = main.s_proj_del({'path': 'notes.txt'})
    data = json.loads(res.body)
    assert data['success'] is False and 'резервную копию' in data['error']
    assert (box / 'notes.txt').exists()


def test_B46_single_delete_blocks_critical(box):
    put(box, 'main.py', 'x = 1')
    put(box, 'MAIN.PY', 'x = 1')
    assert json.loads(main.s_proj_del({'path': 'main.py'}).body)['success'] is False
    assert json.loads(main.s_proj_del({'path': 'MAIN.PY'}).body)['success'] is False
    assert (box / 'main.py').exists()


def test_B47_url_guard_rejects_metadata_and_garbage():
    assert main.validate_url('ftp://example.com/x')[0] is False
    assert main.validate_url('http://')[0] is False
    assert main.validate_url('')[0] is False
    assert main.validate_url(None)[0] is False
    assert main.validate_url('http://user:pw@localhost:11434')[0] is False
    ok, why = main.validate_url('http://169.254.169.254/latest/meta-data')
    assert not ok and 'link-local' in why.lower()
    ok, why = main.validate_url('http://[fe80::1]/')
    assert not ok and 'link-local' in why.lower()
    ok, why = main.validate_url('http://224.0.0.1/x')
    assert not ok and 'зарезервированный' in why
    assert main.validate_url('http://10.0.0.5:8080', allowed_hosts={'api.groq.com'})[0] is False
    assert main.validate_url('http://evil.example.com/v1', allowed_hosts={'api.groq.com'})[0] is False


def test_B47_url_guard_allows_legit():
    assert main.validate_url('http://localhost:11434')[0]
    assert main.validate_url('http://127.0.0.1:11434/api')[0]
    assert main.validate_url('http://192.168.1.20:1234/v1')[0]
    assert main.validate_url('http://10.1.2.3')[0]
    assert main.validate_url('http://8.8.8.8')[0]


def test_B47_ping_blocks_metadata_url():
    st = json.loads(main.s_providers_ping({'providers': [{'id': 'ollama', 'url': 'http://169.254.169.254'}]}).body)['statuses']['ollama']
    assert st['online'] is False and 'отклонён' in st['error']
