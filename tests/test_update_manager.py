import os
import subprocess
from types import SimpleNamespace

import pytest

from core.updater import manager as updater
from api.routes_updates import _check_local_browser_request


def _git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(path, message):
    _git(path, "add", "-A")
    _git(path, "-c", "user.name=Updater Test", "-c", "user.email=updater@example.invalid",
         "commit", "-m", message)


@pytest.fixture
def git_fixture(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    work = tmp_path / "work"
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(seed)], check=True, capture_output=True)
    (seed / "app.txt").write_text("base\n", encoding="utf-8")
    (seed / ".gitignore").write_text("data/updater/\n", encoding="utf-8")
    _commit(seed, "initial")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "main")

    subprocess.run(["git", "clone", str(remote), str(work)], check=True, capture_output=True)
    _git(work, "config", "user.name", "Updater Test")
    _git(work, "config", "user.email", "updater@example.invalid")

    (seed / "remote.txt").write_text("incoming\n", encoding="utf-8")
    _commit(seed, "remote update")
    _git(seed, "push", "origin", "main")

    original_run_git = updater._run_git

    def run_git_for_test(args, timeout=30):
        if args and args[0] == "fetch":
            proc = subprocess.run(
                ["git", "-C", str(work), *args], capture_output=True, text=True,
                timeout=timeout, shell=False, env={**os.environ, "GIT_ALLOW_PROTOCOL": "https:file"},
            )
            return {"ok": proc.returncode == 0, "code": proc.returncode,
                    "stdout": proc.stdout or "", "stderr": proc.stderr or ""}
        return original_run_git(args, timeout)

    monkeypatch.setattr(updater, "_run_git", run_git_for_test)
    monkeypatch.setattr(updater, "BASE", str(work))
    monkeypatch.setattr(updater, "_JOURNAL_DIR", str(journal_dir))
    monkeypatch.setattr(updater, "_JOURNAL_PATH", str(journal_dir / "journal.json"))
    monkeypatch.setattr(updater, "_validate_official_remote", lambda remote_name: None)
    return work


def test_update_preserves_staged_unstaged_and_untracked_changes(git_fixture):
    work = git_fixture
    app = work / "app.txt"
    app.write_text("staged version\n", encoding="utf-8")
    _git(work, "add", "app.txt")
    app.write_text("unstaged version\n", encoding="utf-8")
    (work / "local-note.txt").write_text("private local file\n", encoding="utf-8")

    plan = updater.manager.check()["plan"]
    assert plan["local_changes"] is True
    assert plan["behind"] == 1

    applied = updater.manager.apply(plan["id"])["journal"]
    assert applied["state"] == "CODE_UPDATED"
    assert (work / "remote.txt").read_text(encoding="utf-8") == "incoming\n"
    assert not (work / "local-note.txt").exists()

    prepared = updater.manager.prepare(plan["id"])["journal"]
    assert prepared["state"] == "COMPLETED"
    assert prepared["local_changes_restored"] is True
    assert app.read_text(encoding="utf-8") == "unstaged version\n"
    assert (work / "local-note.txt").read_text(encoding="utf-8") == "private local file\n"
    assert _git(work, "diff", "--cached", "--name-only") == "app.txt"
    assert _git(work, "diff", "--name-only") == "app.txt"
    assert prepared["backup_ref"].startswith("refs/drmaicu/update-backups/")


def test_check_fingerprint_detects_same_path_content_change(git_fixture):
    work = git_fixture
    app = work / "app.txt"
    app.write_text("first local edit\n", encoding="utf-8")
    plan = updater.manager.check()["plan"]
    app.write_text("second local edit\n", encoding="utf-8")

    with pytest.raises(updater.UpdateError) as error:
        updater.manager.apply(plan["id"])
    assert error.value.code == "working_tree_changed"
    assert app.read_text(encoding="utf-8") == "second local edit\n"


def test_update_refuses_local_commits_ahead_of_upstream(git_fixture):
    work = git_fixture
    (work / "local-commit.txt").write_text("local\n", encoding="utf-8")
    _commit(work, "local only")

    plan = updater.manager.check()["plan"]
    assert plan["ahead"] == 1
    assert plan["blockers"]
    with pytest.raises(updater.UpdateError) as error:
        updater.manager.apply(plan["id"])
    assert error.value.code == "update_blocked"


def test_recovery_journal_rejects_corrupt_json(git_fixture):
    with open(updater._JOURNAL_PATH, "w", encoding="utf-8") as stream:
        stream.write("{broken")
    with pytest.raises(updater.UpdateError) as error:
        updater.manager.state()
    assert error.value.code == "journal_corrupt"


def test_check_fingerprint_detects_index_only_change(git_fixture):
    work = git_fixture
    app = work / "app.txt"
    app.write_text("index version A\n", encoding="utf-8")
    _git(work, "add", "app.txt")
    app.write_text("working tree version\n", encoding="utf-8")
    plan = updater.manager.check()["plan"]

    # Меняем только blob в индексе, сохраняя то же содержимое рабочего файла.
    app.write_text("index version B\n", encoding="utf-8")
    _git(work, "add", "app.txt")
    app.write_text("working tree version\n", encoding="utf-8")

    with pytest.raises(updater.UpdateError) as error:
        updater.manager.apply(plan["id"])
    assert error.value.code == "working_tree_changed"
    assert app.read_text(encoding="utf-8") == "working tree version\n"


def test_recovery_journal_rejects_orphan_temp_file(git_fixture):
    with open(updater._JOURNAL_PATH + ".tmp", "w", encoding="utf-8") as stream:
        stream.write('{"schema":1,"state":"APPLYING"}')
    with pytest.raises(updater.UpdateError) as error:
        updater.manager.state()
    assert error.value.code == "journal_temp_orphan"


def test_new_check_cannot_overwrite_pending_restore(git_fixture):
    work = git_fixture
    (work / "local.txt").write_text("keep me\n", encoding="utf-8")
    plan = updater.manager.check()["plan"]
    applied = updater.manager.apply(plan["id"])["journal"]
    backup_ref = applied["backup_ref"]
    bundle = applied["backup_bundle"]
    bundle_path = work / bundle["path"]
    assert bundle_path.is_file()
    assert bundle["size_bytes"] == bundle_path.stat().st_size
    assert _git(work, "bundle", "verify", str(bundle_path))

    with pytest.raises(updater.UpdateError) as error:
        updater.manager.check()
    assert error.value.code == "operation_incomplete"
    assert updater.manager.state()["journal"]["backup_ref"] == backup_ref


def test_git_command_uses_fixed_protocol_allowlist_and_shell_false(monkeypatch):
    captured = {}
    monkeypatch.setattr(updater, "BASE", "/tmp/drmaicu-test-repo")

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    result = updater._run_git(["status"])

    assert result["ok"] is True
    assert captured["argv"] == [
        "git", "-C", "/tmp/drmaicu-test-repo",
        "-c", "protocol.ext.allow=never",
        "-c", "protocol.file.allow=never",
        "status",
    ]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["env"]["GIT_ALLOW_PROTOCOL"] == "https"


def test_update_api_accepts_local_browser_origin():
    from types import SimpleNamespace
    request = SimpleNamespace(
        headers={
            "origin": "http://127.0.0.1:5173",
            "host": "127.0.0.1:8080",
            "sec-fetch-site": "same-origin",
        },
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert _check_local_browser_request(request) is None


def test_update_api_rejects_remote_origin_and_dns_rebinding_host():
    from types import SimpleNamespace
    remote_origin = SimpleNamespace(
        headers={"origin": "https://attacker.example", "host": "127.0.0.1:8080"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    with pytest.raises(updater.UpdateError) as error:
        _check_local_browser_request(remote_origin)
    assert error.value.code == "origin_rejected"

    rebinding_host = SimpleNamespace(
        headers={"origin": "http://localhost:5173", "host": "attacker.example"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    with pytest.raises(updater.UpdateError) as error:
        _check_local_browser_request(rebinding_host)
    assert error.value.code == "host_rejected"


def test_update_api_allows_local_read_without_origin():
    from types import SimpleNamespace
    request = SimpleNamespace(
        headers={"host": "localhost:8080"},
        client=SimpleNamespace(host="::1"),
    )
    assert _check_local_browser_request(request, require_origin=False) is None


def test_restart_required_completes_only_after_new_process(git_fixture, monkeypatch):
    journal = {
        "schema": 1,
        "id": "a" * 32,
        "state": "RESTART_REQUIRED",
        "process_pid": 12345,
        "restart_required": True,
        "remote_head": _git(git_fixture, "rev-parse", "HEAD"),
        "target_version": updater.RUNNING_VERSION,
    }
    updater._save_journal(journal)
    monkeypatch.setattr(updater.os, "getpid", lambda: 54321)

    state = updater.manager.state()["journal"]
    assert state["state"] == "COMPLETED"
    assert state["restart_verified_pid"] == 54321
    assert state["restart_verified_at"]


def test_journal_replace_retries_transient_permission_error(git_fixture, monkeypatch):
    original = updater.os.replace
    calls = []

    def flaky(source, target):
        calls.append(target)
        if len(calls) < 3:
            raise PermissionError("simulated cloud lock")
        return original(source, target)

    monkeypatch.setattr(updater.os, "replace", flaky)
    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    updater._save_journal({"schema": 1, "state": "IDLE"})
    assert len(calls) == 3
    assert updater._load_journal()["state"] == "IDLE"


def test_journal_permanent_permission_error_preserves_temp(git_fixture, monkeypatch):
    def blocked(*args):
        raise PermissionError("simulated cloud lock")

    monkeypatch.setattr(updater.os, "replace", blocked)
    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    with pytest.raises(updater.UpdateError) as error:
        updater._save_journal({"schema": 1, "state": "IDLE"})
    assert error.value.code == "journal_write_blocked"
    assert os.path.isfile(updater._JOURNAL_PATH + ".tmp")


def test_process_lock_released_after_exception(git_fixture):
    with pytest.raises(RuntimeError):
        with updater._process_lock():
            raise RuntimeError("failure")
    with updater._process_lock():
        pass


def test_failure_after_merge_requires_recovery(git_fixture, monkeypatch):
    plan = updater.manager.check()["plan"]
    original = updater._git_ok

    def interrupted(args, timeout=30):
        result = original(args, timeout)
        if args[:2] == ["merge", "--ff-only"]:
            raise updater.UpdateError("simulated interruption")
        return result

    monkeypatch.setattr(updater, "_git_ok", interrupted)
    with pytest.raises(updater.UpdateError):
        updater.manager.apply(plan["id"])
    assert updater.manager.state()["journal"]["state"] == "RECOVERY_REQUIRED"
    recovered = updater.manager.recover(plan["id"])["journal"]
    assert recovered["state"] == "CODE_UPDATED"
    assert recovered["new_head"] == plan["remote_head"]


@pytest.mark.parametrize("failure", ["stash", "update-ref", "bundle", "merge"])
def test_recover_interrupted_backup_sequence(git_fixture, monkeypatch, failure):
    work = git_fixture
    (work / "local-note.txt").write_text("keep me", encoding="utf-8")
    plan = updater.manager.check()["plan"]
    original = updater._git_ok
    hit = False

    def interrupted(args, timeout=30):
        nonlocal hit
        result = original(args, timeout)
        if not hit and args[0] == failure:
            hit = True
            raise updater.UpdateError("simulated interruption")
        return result

    monkeypatch.setattr(updater, "_git_ok", interrupted)
    with pytest.raises(updater.UpdateError):
        updater.manager.apply(plan["id"])
    assert hit
    monkeypatch.setattr(updater, "_git_ok", original)
    recovered = updater.manager.recover(plan["id"])["journal"]
    assert recovered["state"] == ("CODE_UPDATED" if failure == "merge" else "FAILED")
    assert (work / "local-note.txt").read_text(encoding="utf-8") == "keep me"
    assert recovered["backup_verified"]


def test_restart_rejects_wrong_version(git_fixture, monkeypatch):
    updater._save_journal({"schema": 1, "id": "b" * 32, "state": "RESTART_REQUIRED",
                           "process_pid": -1, "remote_head": _git(git_fixture, "rev-parse", "HEAD"),
                           "target_version": "999.0.0"})
    journal = updater.manager.state()["journal"]
    assert journal["state"] == "RESTART_REQUIRED"
    assert journal["error"]


def test_journal_rejects_invalid_backup_ref(git_fixture):
    updater._save_journal({"schema": 1, "id": "b" * 32, "state": "APPLYING",
                           "backup_ref": "refs/heads/main"})
    with pytest.raises(updater.UpdateError) as error:
        updater.manager.state()
    assert error.value.code == "journal_corrupt"


def test_process_lock_excludes_another_process(git_fixture):
    code = ("from core.updater import manager as u; "
            "u._JOURNAL_DIR = " + repr(updater._JOURNAL_DIR) + "; "
            "exec('with u._process_lock(): pass')")
    with updater._process_lock():
        result = subprocess.run([updater.sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        assert result.returncode != 0
        assert "update_locked" in result.stderr or "Другая операция" in result.stderr
    result = subprocess.run([updater.sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_npm_lock_retry(monkeypatch):
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if len(calls) < 3 else 0, stdout="", stderr="npm error EPERM")
    monkeypatch.setattr(updater.subprocess, "run", run)
    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    assert updater._run_environment_step("npm", ["npm", "ci"]).returncode == 0
    assert len(calls) == 3


@pytest.mark.parametrize("label,stderr,count", [("npm", "EPERM", 3), ("npm", "ERESOLVE", 1), ("python", "EPERM", 1)])
def test_environment_retry_is_bounded(monkeypatch, label, stderr, count):
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout="", stderr=stderr)
    monkeypatch.setattr(updater.subprocess, "run", run)
    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    assert updater._run_environment_step(label, ["tool"]).returncode == 1
    assert len(calls) == count


def test_environment_repair_without_reapplying_stash(git_fixture, monkeypatch):
    work = git_fixture
    (work / "local-note.txt").write_text("keep", encoding="utf-8")
    plan = updater.manager.check()["plan"]
    journal = updater.manager.apply(plan["id"])["journal"]
    updater.manager.prepare(plan["id"])
    journal = updater._load_journal()
    journal["state"] = "UPDATE_NEEDS_REPAIR"
    journal["change_summary"]["npm_lock_changed"] = True
    journal["environment_steps"] = [{"step": "npm", "ok": False}]
    updater._save_journal(journal)
    monkeypatch.setattr(updater, "_run_environment_step", lambda *a: SimpleNamespace(returncode=0, stdout="", stderr=""))
    result = updater.manager.prepare(plan["id"])["journal"]
    assert result["state"] == "COMPLETED"
    assert result["environment_steps"][0]["ok"]
    assert (work / "local-note.txt").read_text(encoding="utf-8") == "keep"


def test_no_update_is_not_blocker(git_fixture):
    plan = updater.manager.check()["plan"]
    updater.manager.apply(plan["id"])
    updater.manager.prepare(plan["id"])
    plan = updater.manager.check()["plan"]
    assert plan["up_to_date"] is True
    assert not plan["blockers"]
    with pytest.raises(updater.UpdateError) as exc:
        updater.manager.apply(plan["id"])
    assert exc.value.code == "no_update"
    assert updater.manager.history()["history"][0]["state"] == "COMPLETED"


def test_progress_reads_during_operation_lock(git_fixture):
    updater._save_journal({"schema": 1, "id": "a" * 32, "state": "PREPARING", "active_step": "npm"})
    with updater._process_lock():
        assert updater.manager.progress()["progress"]["active_step"] == "npm"


def test_history_does_not_store_command_output(git_fixture):
    updater._archive_terminal({"id": "a" * 32, "state": "FAILED", "updated_at": "2026-11-27",
                               "error": "private", "environment_steps": [{"step": "npm", "ok": False, "stderr": "private"}]})
    record = updater.manager.history()["history"][0]
    assert "error" not in record
    assert "stderr" not in record["environment_steps"][0]


def test_restart_request_only_for_prepared_operation(git_fixture):
    with pytest.raises(updater.UpdateError):
        updater.manager.request_restart("a" * 32)
    assert not (git_fixture / "restart.flag").exists()
    updater._save_journal({"schema": 1, "id": "a" * 32, "state": "RESTART_REQUIRED"})
    assert updater.manager.request_restart("a" * 32)["success"]
    assert (git_fixture / "restart.flag").read_text() == "update restart"


def test_restart_rejects_wrong_operation_id(git_fixture):
    updater._save_journal({"schema": 1, "id": "a" * 32, "state": "RESTART_REQUIRED"})
    with pytest.raises(updater.UpdateError):
        updater.manager.request_restart("b" * 32)
    assert not (git_fixture / "restart.flag").exists()
