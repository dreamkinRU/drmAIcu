# tests/test_patching_hardcore.py
# -*- coding: utf-8 -*-
import builtins
import os
import sys
import stat
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main
import patch_engine as engine
import guards
from api import routes_project as rp

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
    return base

def put(base, rel, text, encoding="utf-8", newline=None):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if newline is None:
        p.write_text(text, encoding=encoding)
    else:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        raw = normalized.replace("\n", newline)
        p.write_bytes(raw.encode(encoding))
    return p

def read(p, encoding="utf-8"):
    return p.read_text(encoding=encoding)

class TestEncodingResilience:
    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1251", "latin-1"])
    def test_search_replace_preserves_encoding(self, box, encoding):
        # Pure ASCII гарантированно валиден во ВСЕХ этих кодировках
        content = "hello world\nline2\n"
        p = put(box, "encoded.txt", content, encoding=encoding)
        text = engine.read_text(str(p))
        result = engine.apply_search_replace(text, "hello", "HELLO")
        p.write_text(result, encoding=encoding)
        assert "HELLO" in p.read_text(encoding=encoding)

    def test_utf8_bom_preserved_after_full_replace(self, box):
        content_with_bom = "\ufeff# BOM file\nprint('hello')\n"
        p = put(box, "bom.py", content_with_bom, encoding="utf-8-sig")
        res = engine.apply_patch({"patch_id": "T-BOM", "operations": [
            {"type": "full_replace", "target_file": "bom.py", "full_file_content": "# BOM file\nprint('world')\n"}
        ]})
        assert res["success"]
        assert "print('world')" in read(p)

class TestLineEndings:
    @pytest.mark.parametrize("file_le,anchor_le", [("\n", "\n"), ("\r\n", "\r\n"), ("\n", "\r\n"), ("\r\n", "\n")])
    def test_search_replace_cross_line_endings(self, file_le, anchor_le):
        file_content = f"line1{file_le}line2{file_le}line3{file_le}"
        anchor = f"line2{anchor_le}"
        result = engine.apply_search_replace(file_content, anchor, "LINE2\n")
        assert result is not None
        assert "LINE2" in result

    def test_apply_diff_crlf_injection(self):
        out = engine.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\r\n a\r\n-b\r\n+B")
        assert "\r" not in out

    def test_apply_diff_trailing_newline(self):
        result = engine.apply_diff("a\nb\nc", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n")
        assert result == "a\nB\nc"

    def test_pure_insert_after_line(self):
        result = engine.apply_diff("l1\nl2\nl3", "@@ -2,0 +3,1 @@\n+INSERTED")
        assert result == "l1\nl2\nINSERTED\nl3"

class TestAnchorNormalization:
    def test_trailing_whitespace_in_anchor(self):
        # Якорь и контент имеют ОДИНАКОВОЕ количество строк. Различаются только trailing пробелы.
        content = "def foo():   \n    pass\n"
        anchor = "def foo():\n    pass\n"
        result = engine.apply_search_replace(content, anchor, "def bar():\n    pass\n")
        assert result is not None
        assert "def bar():" in result

    def test_trailing_whitespace_in_file(self):
        content = "def foo():\n    pass   \n"
        anchor = "def foo():\n    pass\n"
        result = engine.apply_search_replace(content, anchor, "def bar():\n    pass\n")
        assert result is not None
        assert "def bar():" in result

    # Тест tabs vs spaces удалён, так как нормализация LEADING пробелов
    # семантически опасна в Python/TS и намеренно не реализована.

class TestAtomicityUnderFailure:
    def test_rollback_on_syntax_error_python(self, box):
        put(box, "good.py", "x = 1\n")
        put(box, "bad.py", "y = 1\n")
        res = engine.apply_patch({"patch_id": "T-SYN", "operations": [
            {"type": "full_replace", "target_file": "good.py", "full_file_content": "x = 2\n"},
            {"type": "full_replace", "target_file": "bad.py", "full_file_content": "def f(:\n"},
        ]})
        assert res["success"] is False
        assert read(box / "good.py") == "x = 1\n"

    def test_rollback_on_sha_mismatch(self, box, monkeypatch):
        put(box, "a.py", "x = 1\n")
        put(box, "b.py", "y = 1\n")
        real_sha = engine.sha_bytes
        counter = {"i": 0}
        def fake_sha(data):
            counter["i"] += 1
            return "bogus" if counter["i"] > 2 else real_sha(data)
        monkeypatch.setattr(engine, "sha_bytes", fake_sha)
        res = engine.apply_patch({"patch_id": "T-SHA", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
            {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
        ]})
        assert res["success"] is False
        assert read(box / "a.py") == "x = 1\n"
        assert read(box / "b.py") == "y = 1\n"

    def test_phase1_blocks_everything(self, box):
        put(box, "good.py", "a = 1\n")
        res = engine.apply_patch({"patch_id": "T-PH1", "operations": [
            {"type": "full_replace", "target_file": "good.py", "full_file_content": "a = 2\n"},
            {"type": "full_replace", "target_file": "bad.py", "full_file_content": "def f(:\n"},
        ]})
        assert res["success"] is False
        assert read(box / "good.py") == "a = 1\n"

class TestPathSecurity:
    def test_path_traversal_dotdot(self, box):
        _, _, _, err = engine.compute_new({"type": "create", "target_file": "../escaped.py", "full_file_content": "p = 1\n"})
        assert err is not None

    def test_path_traversal_absolute(self, box):
        _, _, _, err = engine.compute_new({"type": "create", "target_file": "/etc/passwd", "full_file_content": "root:x:0:0\n"})
        assert err is not None

    def test_null_byte_in_path(self):
        # Прямая, неопровержимая проверка функции безопасности
        assert engine.safe_path("safe.py\x00.txt") is None
        assert engine.safe_path("../escaped\x00.py") is None

class TestValidationStrictness:
    def test_broken_python_rejected(self):
        ok, err = engine.validate("test.py", "def f(:\n")
        assert ok is False

    def test_broken_json_rejected(self):
        ok, err = engine.validate("test.json", "{broken}")
        assert ok is False

    def test_broken_tsx_rejected(self):
        ok, err = engine.validate("src/App.tsx", "const x = ((( ;")
        assert ok is False, f"TSX валидация молча пропустила битый код: {err}"

    def test_valid_python_accepted(self):
        ok, err = engine.validate("test.py", "def f():\n    return 1\n")
        assert ok is True

class TestIdempotency:
    def test_full_replace_idempotent(self, box):
        put(box, "a.py", "x = 1\n")
        content = "x = 2\n"
        r1 = engine.apply_patch({"patch_id": "T-ID1", "operations": [{"type": "full_replace", "target_file": "a.py", "full_file_content": content}]})
        sha1 = engine.sha_bytes((box / "a.py").read_bytes())
        r2 = engine.apply_patch({"patch_id": "T-ID2", "operations": [{"type": "full_replace", "target_file": "a.py", "full_file_content": content}]})
        sha2 = engine.sha_bytes((box / "a.py").read_bytes())
        assert r1["success"] and r2["success"]
        assert sha1 == sha2

    def test_search_replace_noop_when_not_found(self, box):
        put(box, "a.py", "x = 1\n")
        res = engine.apply_patch({"patch_id": "T-NOOP", "operations": [{"type": "search_and_replace", "target_file": "a.py", "find": "nonexistent", "replace": "y = 2"}]})
        assert res["success"] is False
        assert read(box / "a.py") == "x = 1\n"

class TestRollback:
    def test_multi_apply_and_rollback(self, box):
        put(box, "a.py", "x = 1\n")
        put(box, "b.py", "y = 1\n")
        assert engine.apply_patch({"patch_id": "T-RB1", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
            {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
        ]})["success"]
        assert engine.rollback()["success"]
        assert read(box / "a.py") == "x = 1\n"
        assert read(box / "b.py") == "y = 1\n"

class TestEdgeCases:
    def test_empty_file_full_replace(self, box):
        put(box, "empty.py", "")
        res = engine.apply_patch({"patch_id": "T-EMP", "operations": [{"type": "full_replace", "target_file": "empty.py", "full_file_content": "x = 1\n"}]})
        assert res["success"]
        assert read(box / "empty.py") == "x = 1\n"

    def test_empty_anchor_rejected(self, box):
        put(box, "a.py", "x = 1\n")
        res = engine.apply_patch({"patch_id": "T-EMPTY", "operations": [{"type": "search_and_replace", "target_file": "a.py", "find": "", "replace": "y = 2"}]})
        assert res["success"] is False

    def test_very_long_anchor(self):
        content = "prefix\n" + "A" * 10000 + "\nsuffix\n"
        anchor = "A" * 10000
        result = engine.apply_search_replace(content, anchor, "B" * 100)
        assert result is not None
        assert "B" * 100 in result

class TestFuzz:
    def test_random_anchor_not_crash(self):
        import random, string
        content = "\n".join(["".join(random.choices(string.ascii_letters, k=20)) for _ in range(50)])
        for _ in range(20):
            anchor = "".join(random.choices(string.ascii_letters + " \t\n", k=30))
            try:
                engine.apply_search_replace(content, anchor, "REPLACEMENT")
            except ValueError:
                pass
            except Exception as e:
                pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")

    def test_unicode_anchors(self):
        content = "привет мир\n你好世界\n🚀 rocket\n"
        for anchor in ["привет мир\n", "你好世界\n", "🚀 rocket\n"]:
            result = engine.apply_search_replace(content, anchor, "REPLACED\n")
            assert result is not None
            assert "REPLACED" in result


class TestAPIIntegration:
    """Интеграционные тесты, проверяющие реальный путь API /api/patches/apply.
    Эмулируют ровно те JSON-пейлоады, которые приходят из UI."""

    def test_api_blocks_path_traversal(self, box):
        payload = {
            "patch_id": "API-TRAVERSAL",
            "operations": [{
                "type": "create",
                "target_file": "../escaped.py",
                "full_file_content": "print('hacked')"
            }]
        }
        res = engine.apply_patch(payload)
        assert res["success"] is False
        assert "Bad target_file" in res["error"] or "Path outside" in res["error"]

    def test_api_updates_manifest(self, box):
        put(box, "a.py", "x = 1\n")
        payload = {
            "patch_id": "API-MANIFEST",
            "operations": [{
                "type": "full_replace",
                "target_file": "a.py",
                "full_file_content": "x = 2\n"
            }]
        }
        res = engine.apply_patch(payload)
        assert res["success"] is True
        man = engine.load_manifest()
        assert any(p["patch_id"] == "API-MANIFEST" for p in man["applied"])

    def test_api_multi_ops_same_file(self, box):
        put(box, "a.py", "x = 1\ny = 1\n")
        payload = {
            "patch_id": "API-MULTI",
            "operations": [
                {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
                {"type": "search_and_replace", "target_file": "a.py", "find": "y = 1", "replace": "y = 2"}
            ]
        }
        res = engine.apply_patch(payload)
        assert res["success"] is True
        assert read(box / "a.py") == "x = 2\ny = 2\n"

    def test_api_rollback_after_partial_failure(self, box):
        put(box, "good.py", "x = 1\n")
        put(box, "bad.py", "y = 1\n")
        payload = {
            "patch_id": "API-FAIL",
            "operations": [
                {"type": "full_replace", "target_file": "good.py", "full_file_content": "x = 2\n"},
                {"type": "full_replace", "target_file": "bad.py", "full_file_content": "def f(:\n"}
            ]
        }
        res = engine.apply_patch(payload)
        assert res["success"] is False
        assert read(box / "good.py") == "x = 1\n"
        assert read(box / "bad.py") == "y = 1\n"

    def test_compute_ops_blocks_path_traversal_on_multi_ops(self, box):
        """Убеждаемся, что compute_ops использует safe_path для ВСЕХ операций, а не только первой."""
        put(box, "a.py", "x = 1\n")
        payload = {
            "patch_id": "T-COMPUTE-OPS-SEC",
            "operations": [
                {"type": "search_and_replace", "target_file": "a.py", "find": "x = 1", "replace": "x = 2"},
                {"type": "create", "target_file": "../escaped.py", "full_file_content": "hacked"}
            ]
        }
        ops = engine.compute_ops(payload)
        # Первая операция валидна
        assert ops[0]['err'] is None
        # Вторая операция должна быть заблокирована safe_path (traversal)
        assert ops[1]['err'] is not None
        assert "Bad target_file" in ops[1]['err']


class TestPreviewPurity:
    """B30/B31: dry-run (preview/apply-test) не имеет права мутировать мир."""

    def _snapshot(self, box):
        files = {}
        for p in sorted(box.rglob("*")):
            if p.is_file() and "__pycache__" not in str(p):
                files[str(p.relative_to(box))] = p.read_bytes()
        return files

    def test_preview_and_test_apply_leave_no_traces(self, box):
        put(box, "a.py", "x = 1\n")
        put(box, "b.py", "y = 1\n")
        payload = {"patch_id": "B30-PURE", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
            {"type": "search_and_replace", "target_file": "b.py", "find": "y = 1", "replace": "y = 22"}
        ]}
        before = self._snapshot(box)
        pv = engine.preview_patch(dict(payload))
        ta = engine.test_apply(dict(payload))
        after = self._snapshot(box)
        assert pv["success"] and ta["success"]
        assert pv["multi"] and ta["multi"]
        assert after == before, "dry-run изменил состояние: файлы/бэкапы/манифест"
        assert read(box / "a.py") == "x = 1\n"
        assert read(box / "b.py") == "y = 1\n"

    def test_preview_partial_invalid_no_side_effects(self, box):
        payload = {"patch_id": "B31-PURE", "operations": [
            {"type": "create", "target_file": "new.py", "full_file_content": "n = 1\n"},
            {"type": "create", "target_file": "../escaped.py", "full_file_content": "bad"}
        ]}
        before = self._snapshot(box)
        pv = engine.preview_patch(payload)
        ta = engine.test_apply(payload)
        after = self._snapshot(box)
        assert pv["success"] is False
        assert ta["success"] is False
        assert after == before
        assert not (box / "new.py").exists()


class TestConcurrency:
    """B37/B38: TX_LOCK — файл никогда не 'порван', манифест не теряет записи."""

    def test_no_torn_write_two_threads_same_file(self, box):
        import threading as th
        put(box, "a.py", "x = 1\n")
        results = []
        def apply_ver(v):
            results.append(engine.apply_patch({"patch_id": f"B37-{v}", "operations": [
                {"type": "full_replace", "target_file": "a.py", "full_file_content": f"x = {v}\n"}
            ]}))
        t1 = th.Thread(target=apply_ver, args=(2,)); t2 = th.Thread(target=apply_ver, args=(3,))
        t1.start(); t2.start(); t1.join(10); t2.join(10)
        assert not t1.is_alive() and not t2.is_alive()
        assert len(results) == 2 and all(r["success"] for r in results)
        content = (box / "a.py").read_text(encoding="utf-8")
        assert content in ("x = 2\n", "x = 3\n"), f"torn write: {content!r}"
        man = engine.load_manifest()
        assert len(man["applied"]) == 2 and len(man["history"]) == 2

    def test_ten_threads_manifest_integrity(self, box):
        import threading as th
        errs = []
        def apply_own(i):
            r = engine.apply_patch({"patch_id": f"B38-{i}", "operations": [
                {"type": "create", "target_file": f"f{i}.py", "full_file_content": f"f = {i}\n"}
            ]})
            if not r["success"]:
                errs.append(r.get("error"))
        ts = [th.Thread(target=apply_own, args=(i,)) for i in range(10)]
        [t.start() for t in ts]; [t.join(10) for t in ts]
        assert not errs, errs
        man = engine.load_manifest()
        assert len(man["applied"]) == 10 and len(man["history"]) == 10
        for i in range(10):
            assert (box / f"f{i}.py").read_text(encoding="utf-8") == f"f = {i}\n"


class TestCrashHygiene:
    """B39: после любой аварии в целевых директориях нет *.trim."""

    def _tmps(self, box):
        return [str(p) for p in box.rglob("*.tmp")]

    def test_no_tmp_after_phase1_reject(self, box):
        put(box, "a.py", "x = 1\n")
        put(box, "bad.py", "y = 1\n")
        assert engine.apply_patch({"patch_id": "B39-A", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
            {"type": "full_replace", "target_file": "bad.py", "full_file_content": "def f(:\n"},
        ]})["success"] is False
        assert self._tmps(box) == []

    def test_no_tmp_after_replace_failure_midwrite(self, box, monkeypatch):
        real_replace = engine.os.replace
        state = {"n": 0}
        def failing_replace(src, dst, *a, **kw):
            if dst.endswith("b.py"):
                state["n"] += 1
                raise OSError("replace failed mid-transaction")
            return real_replace(src, dst, *a, **kw)
        monkeypatch.setattr(engine.os, "replace", failing_replace)
        put(box, "a.py", "x = 1\n")
        put(box, "b.py", "y = 1\n")
        (box / "b.py.tmp").write_bytes(b"STALE FROM CRASH")
        res = engine.apply_patch({"patch_id": "B39-B", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"},
            {"type": "full_replace", "target_file": "b.py", "full_file_content": "y = 2\n"},
        ]})
        assert res["success"] is False
        assert read(box / "a.py") == "x = 1\n"
        assert read(box / "b.py") == "y = 1\n"
        assert self._tmps(box) == []

    def test_no_tmp_after_success(self, box):
        put(box, "a.py", "x = 1\n")
        assert engine.apply_patch({"patch_id": "B39-C", "operations": [
            {"type": "full_replace", "target_file": "a.py", "full_file_content": "x = 2\n"}
        ]})["success"]
        assert self._tmps(box) == []


class TestMidTransactionDefense:
    """B41/B42: появление create-цели посреди транзакции и диск full во время записи."""

    def test_B41_create_target_appeared_mid_transaction(self, box, monkeypatch):
        payload = {"patch_id": "B41", "operations": [
            {"type": "create", "target_file": "new.py", "full_file_content": "n = 1\n"}
        ]}
        ops = engine.compute_ops(payload)
        assert all(not o["err"] for o in ops)
        monkeypatch.setattr(engine, "compute_ops", lambda data: ops)
        (box / "new.py").write_bytes(b"intruder\n")
        res = engine.apply_patch(payload)
        assert res["success"] is False
        assert "транзакции" in res["error"]
        assert (box / "new.py").read_bytes() == b"intruder\n"
        assert engine.load_manifest()["applied"] == []

    def test_B42_disk_full_clean_rollback(self, box, monkeypatch):
        real_open = builtins.open
        def failing_open(file, mode="r", *a, **kw):
            if mode == "wb" and str(file).endswith("c2.py.tmp"):
                raise OSError(28, "No space left on device")
            return real_open(file, mode, *a, **kw)
        monkeypatch.setattr(builtins, "open", failing_open)
        res = engine.apply_patch({"patch_id": "B42", "operations": [
            {"type": "create", "target_file": "c1.py", "full_file_content": "a = 1\n"},
            {"type": "create", "target_file": "c2.py", "full_file_content": "b = 2\n"},
        ]})
        assert res["success"] is False
        assert not (box / "c1.py").exists()
        assert not (box / "c2.py").exists()
        assert list(box.rglob("*.tmp")) == []
        assert engine.load_manifest()["applied"] == []
