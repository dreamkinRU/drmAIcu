# tests/test_engine.py
import importlib
import pytest

main = importlib.import_module("main")


@pytest.fixture
def box(tmp_path, monkeypatch):
    base = tmp_path / "proj"
    (base / "patch" / "archive").mkdir(parents=True)
    (base / "backups").mkdir()
    (base / "project_archive").mkdir()
    monkeypatch.setattr(main, "BASE", str(base))
    monkeypatch.setattr(main, "PATCH_DIR", str(base / "patch"))
    monkeypatch.setattr(main, "ARCHIVE_DIR", str(base / "patch" / "archive"))
    monkeypatch.setattr(main, "BACKUP_DIR", str(base / "backups"))
    monkeypatch.setattr(main, "PROJ_ARCHIVE", str(base / "project_archive"))
    monkeypatch.setattr(main, "MANIFEST", str(base / "patch_manifest.json"))
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
    _, _, err = main.compute_new(
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
    real, n = main.sha, {"i": 0}

    def fake(text):
        n["i"] += 1
        return "bogus" if n["i"] > 2 else real(text)

    monkeypatch.setattr(main, "sha", fake)
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
    _, _, err = main.compute_new(
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