import os
import subprocess

import pytest

from core.updater import manager as updater


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
