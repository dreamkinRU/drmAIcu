import importlib

updater = importlib.import_module("core.updater.manager")


def test_versions_independent_of_journal(monkeypatch):
    def git(args):
        return {"HEAD": "local", "refs/remotes/origin/main": "remote"}[args[-1]]
    monkeypatch.setattr(updater, "_git_ok", git)
    monkeypatch.setattr(updater, "_version_or_none", lambda head: {"local": "3.19.8", "remote": "3.19.9"}[head])
    def forbidden():
        raise AssertionError("must not read journal")
    monkeypatch.setattr(updater, "_load_journal", forbidden)
    assert updater.manager.versions()["versions"] == {
        "running": updater.RUNNING_VERSION, "installed": "3.19.8", "cached_remote": "3.19.9"}


def test_versions_missing_remote(monkeypatch):
    def git(args):
        if args[-1] != "HEAD":
            raise updater.UpdateError("missing ref")
        return "local"
    monkeypatch.setattr(updater, "_git_ok", git)
    monkeypatch.setattr(updater, "_version_or_none", lambda head: "3.19.8")
    result = updater.manager.versions()["versions"]
    assert result["installed"] == "3.19.8"
    assert result["cached_remote"] is None
