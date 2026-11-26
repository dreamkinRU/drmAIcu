# -*- coding: utf-8 -*-
"""Безопасный менеджер обновлений drmAIcu.

Update Manager намеренно отделён от Repos Sync: он никогда не делает add,
commit, push, rebase или reset. Локальные изменения сохраняются в отдельную
refs/drmaicu/update-backups/<id> и восстанавливаются через stash apply --index.
"""
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from api.shared import BASE
from plugins.repos import git_service

_LOCK = threading.RLock()
_ALLOWED_REMOTE_HOST = "github.com"
_ALLOWED_REMOTE_PATH = "/dreamkinRU/drmAIcu"
_JOURNAL_DIR = os.path.join(BASE, "data", "updater")
_JOURNAL_PATH = os.path.join(_JOURNAL_DIR, "journal.json")
_TIMEOUT = 180


class UpdateError(RuntimeError):
    def __init__(self, message, code="update_error", status=409):
        super().__init__(message)
        self.code = code
        self.status = status


def _now():
    return datetime.now(timezone.utc).isoformat()


def _run_git(args, timeout=30):
    """Запуск только сформированных внутри модуля Git-команд; shell всегда выключен."""
    argv = ["git", "-C", BASE] + [str(item) for item in args]
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        proc = subprocess.run(
            argv, cwd=BASE, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, shell=False, env=env,
        )
    except subprocess.TimeoutExpired:
        raise UpdateError("Git operation timed out", "git_timeout", 504)
    except OSError as exc:
        raise UpdateError("Cannot start Git: %s" % exc, "git_unavailable", 503)
    return {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def _git_ok(args, timeout=30):
    result = _run_git(args, timeout)
    if not result["ok"]:
        detail = (result["stderr"] or result["stdout"]).strip()
        raise UpdateError(detail[:3000] or "Git command failed", "git_failed", 409)
    return result["stdout"].strip()


def _load_journal():
    try:
        with open(_JOURNAL_PATH, "r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or data.get("schema") != 1:
            raise ValueError("unknown journal schema")
        return data
    except FileNotFoundError:
        return {"schema": 1, "state": "IDLE", "updated_at": _now()}
    except Exception as exc:
        raise UpdateError(
            "Журнал обновления повреждён; автоматическое продолжение запрещено: %s" % exc,
            "journal_corrupt", 423,
        )


def _save_journal(data):
    os.makedirs(_JOURNAL_DIR, exist_ok=True)
    data["updated_at"] = _now()
    temp = _JOURNAL_PATH + ".tmp"
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with open(temp, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, _JOURNAL_PATH)


def _repo_lock():
    return git_service.repo_operation_lock(BASE)


def _status():
    return _git_ok(["status", "--porcelain=v2", "--branch", "--untracked-files=all"])


def _branch_and_upstream():
    branch = _git_ok(["symbolic-ref", "--quiet", "--short", "HEAD"])
    upstream = _git_ok(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if "/" not in upstream:
        raise UpdateError("Upstream не распознан: %s" % upstream, "upstream_invalid")
    remote, remote_branch = upstream.split("/", 1)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", remote):
        raise UpdateError("Недопустимое имя remote", "remote_invalid")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", remote_branch) or ".." in remote_branch:
        raise UpdateError("Недопустимое имя upstream-ветки", "branch_invalid")
    return branch, upstream, remote, remote_branch


def _validate_official_remote(remote):
    url = _git_ok(["remote", "get-url", remote])
    parsed = urlparse(url)
    path = (parsed.path or "").rstrip("/")
    if (parsed.scheme != "https" or parsed.hostname != _ALLOWED_REMOTE_HOST
            or parsed.username or parsed.password
            or path.removesuffix(".git") != _ALLOWED_REMOTE_PATH):
        raise UpdateError(
            "Обновление разрешено только из официального HTTPS-репозитория "
            "https://github.com/dreamkinRU/drmAIcu. Текущий remote не прошёл проверку.",
            "remote_not_trusted", 403,
        )


def _changed_files(status_text):
    files = []
    for line in status_text.splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("1 ") or line.startswith("2 "):
            parts = line.split(" ")
            if len(parts) >= 9:
                files.append(parts[8])
        elif line.startswith("? "):
            files.append(line[2:])
        elif line.startswith("u "):
            parts = line.split(" ")
            if len(parts) >= 11:
                files.append(parts[10])
    return sorted(set(files))


def _read_update_diff(old_head, new_head):
    result = _run_git(["diff", "--name-only", old_head, new_head], 30)
    if not result["ok"]:
        raise UpdateError("Не удалось определить изменённые файлы обновления", "diff_failed")
    files = sorted({line.strip() for line in result["stdout"].splitlines() if line.strip()})
    return {
        "files": files,
        "python_changed": any(name.endswith(".py") for name in files),
        "requirements_changed": "requirements.txt" in files,
        "npm_lock_changed": "package-lock.json" in files,
        "frontend_changed": any(name.startswith("src/") or name in ("vite.config.js", "package.json") for name in files),
    }


class UpdateManager:
    """Трёхэтапный процесс с устойчивым журналом и явными барьерами подтверждения."""

    def state(self):
        with _LOCK:
            journal = _load_journal()
            return {"success": True, "journal": journal}

    def check(self):
        with _LOCK, _repo_lock():
            journal = _load_journal()
            if journal.get("state") in ("APPLYING", "RESTORING", "PREPARING", "RECOVERY_REQUIRED", "UPDATE_NEEDS_REPAIR"):
                raise UpdateError(
                    "Есть незавершённая операция (%s). Сначала завершите восстановление." % journal.get("state"),
                    "operation_incomplete", 423,
                )
            branch, upstream, remote, remote_branch = _branch_and_upstream()
            _validate_official_remote(remote)
            before_status = _status()
            old_head = _git_ok(["rev-parse", "HEAD"])
            _git_ok(["fetch", "--no-tags", remote, remote_branch], _TIMEOUT)
            remote_ref = "refs/remotes/%s/%s" % (remote, remote_branch)
            remote_head = _git_ok(["rev-parse", "--verify", remote_ref])
            counts = _git_ok(["rev-list", "--left-right", "--count", "HEAD...%s" % remote_ref])
            parts = counts.split()
            if len(parts) != 2:
                raise UpdateError("Не удалось определить ahead/behind", "compare_failed")
            ahead, behind = int(parts[0]), int(parts[1])
            incoming = []
            if behind:
                raw = _git_ok(["log", "--format=%H%x1f%s", "HEAD..%s" % remote_ref, "-n", "100"])
                for line in raw.splitlines():
                    sha, sep, subject = line.partition("\x1f")
                    incoming.append({"sha": sha, "subject": subject if sep else ""})
            plan = {
                "id": uuid.uuid4().hex,
                "state": "CHECKED",
                "created_at": _now(),
                "branch": branch,
                "upstream": upstream,
                "remote": remote,
                "remote_branch": remote_branch,
                "old_head": old_head,
                "remote_head": remote_head,
                "ahead": ahead,
                "behind": behind,
                "local_changes": bool(_changed_files(before_status)),
                "local_files": _changed_files(before_status),
                "status_fingerprint": before_status,
                "incoming_commits": incoming,
                "blockers": [],
            }
            if ahead:
                plan["blockers"].append("Локальная ветка содержит собственные коммиты (ahead=%s)." % ahead)
            if not behind:
                plan["blockers"].append("Нет входящих коммитов для обновления.")
            journal = plan
            _save_journal(journal)
            return {"success": True, "plan": journal}

    def apply(self, operation_id):
        with _LOCK, _repo_lock():
            journal = _load_journal()
            if journal.get("state") != "CHECKED" or journal.get("id") != operation_id:
                raise UpdateError("План устарел или отсутствует. Выполните повторную проверку.", "plan_stale")
            if journal.get("blockers"):
                raise UpdateError("Обновление заблокировано: " + " ".join(journal["blockers"]), "update_blocked")
            if _git_ok(["rev-parse", "HEAD"]) != journal.get("old_head"):
                raise UpdateError("HEAD изменился после проверки. Повторите шаг 1.", "plan_stale")
            current_status = _status()
            if current_status != journal.get("status_fingerprint"):
                raise UpdateError("Рабочее дерево изменилось после проверки. Повторите шаг 1.", "working_tree_changed")

            journal["state"] = "APPLYING"
            journal["backup_ref"] = None
            _save_journal(journal)
            try:
                if journal.get("local_changes"):
                    backup_id = journal["id"]
                    message = "drmAIcu-update-backup:" + backup_id
                    _git_ok(["stash", "push", "--include-untracked", "--message", message], _TIMEOUT)
                    stash_oid = _git_ok(["rev-parse", "--verify", "refs/stash"])
                    backup_ref = "refs/drmaicu/update-backups/" + backup_id
                    _git_ok(["update-ref", backup_ref, stash_oid])
                    _git_ok(["cat-file", "-e", backup_ref + "^{commit}"])
                    if _status().strip():
                        raise UpdateError("После резервирования рабочее дерево не стало чистым", "backup_incomplete")
                    journal["backup_ref"] = backup_ref
                    journal["backup_oid"] = stash_oid
                    journal["backup_verified"] = True
                    _save_journal(journal)
                _git_ok(["merge", "--ff-only", journal["remote_head"]], _TIMEOUT)
                new_head = _git_ok(["rev-parse", "HEAD"])
                if new_head != journal["remote_head"]:
                    raise UpdateError("HEAD после fast-forward не совпал с целевой версией", "head_mismatch")
                journal["new_head"] = new_head
                journal["change_summary"] = _read_update_diff(journal["old_head"], new_head)
                journal["state"] = "CODE_UPDATED"
                _save_journal(journal)
                return {"success": True, "journal": journal}
            except Exception as exc:
                journal["state"] = "RECOVERY_REQUIRED" if journal.get("backup_ref") else "FAILED"
                journal["error"] = str(exc)[:3000]
                _save_journal(journal)
                raise

    def prepare(self, operation_id):
        with _LOCK, _repo_lock():
            journal = _load_journal()
            if journal.get("id") != operation_id or journal.get("state") != "CODE_UPDATED":
                raise UpdateError("Шаг 2 ещё не завершён или операция устарела.", "invalid_state")
            journal["state"] = "RESTORING"
            _save_journal(journal)
            try:
                if journal.get("backup_ref"):
                    if _status().strip():
                        raise UpdateError(
                            "После обновления появились новые локальные изменения. "
                            "Автоматическое восстановление остановлено, резервная копия сохранена.",
                            "restore_worktree_dirty",
                        )
                    result = _run_git(["stash", "apply", "--index", journal["backup_ref"]], _TIMEOUT)
                    if not result["ok"]:
                        raise UpdateError(
                            "Не удалось восстановить локальные изменения без конфликтов. "
                            "Резервная копия сохранена: %s. %s" %
                            (journal["backup_ref"], (result["stderr"] or result["stdout"]).strip()[:2000]),
                            "restore_conflict",
                        )
                    journal["local_changes_restored"] = True
                else:
                    journal["local_changes_restored"] = True

                summary = journal.get("change_summary") or {}
                commands = []
                if summary.get("requirements_changed"):
                    commands.append(("python", [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]))
                if summary.get("npm_lock_changed"):
                    npm = "npm.cmd" if os.name == "nt" else "npm"
                    commands.append(("npm", [npm, "ci", "--no-audit", "--no-fund"]))
                if summary.get("frontend_changed"):
                    npm = "npm.cmd" if os.name == "nt" else "npm"
                    commands.append(("frontend_build", [npm, "run", "build"]))
                results = []
                for label, argv in commands:
                    try:
                        proc = subprocess.run(
                            argv, cwd=BASE, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=900,
                            shell=False, env={**os.environ, "CI": "1", "GIT_TERMINAL_PROMPT": "0"},
                        )
                        results.append({
                            "step": label, "ok": proc.returncode == 0,
                            "code": proc.returncode,
                            "stdout": (proc.stdout or "")[-8000:],
                            "stderr": (proc.stderr or "")[-8000:],
                        })
                        if proc.returncode != 0:
                            raise UpdateError("%s завершился с кодом %s" % (label, proc.returncode), "environment_failed")
                    except subprocess.TimeoutExpired:
                        raise UpdateError("%s: превышено время ожидания" % label, "environment_timeout", 504)
                journal["environment_steps"] = results
                journal["restart_required"] = bool(summary.get("python_changed"))
                journal["state"] = "COMPLETED"
                _save_journal(journal)
                return {"success": True, "journal": journal}
            except Exception as exc:
                journal["state"] = "UPDATE_NEEDS_REPAIR"
                journal["error"] = str(exc)[:3000]
                _save_journal(journal)
                raise

    def recover(self, operation_id):
        """Повторная попытка восстановления исходных локальных изменений."""
        with _LOCK, _repo_lock():
            journal = _load_journal()
            if journal.get("id") != operation_id or journal.get("state") not in (
                "RECOVERY_REQUIRED", "UPDATE_NEEDS_REPAIR", "RESTORING"
            ):
                raise UpdateError("Нет операции, требующей восстановления.", "invalid_state")
            backup_ref = journal.get("backup_ref")
            if not backup_ref:
                raise UpdateError("Резервная копия для восстановления не найдена.", "backup_missing")
            if _status().strip():
                raise UpdateError(
                    "Рабочее дерево не чистое. Сначала сохраните или устраните новые изменения вручную.",
                    "working_tree_dirty",
                )
            result = _run_git(["stash", "apply", "--index", backup_ref], _TIMEOUT)
            if not result["ok"]:
                journal["state"] = "RECOVERY_REQUIRED"
                journal["error"] = (result["stderr"] or result["stdout"]).strip()[:3000]
                _save_journal(journal)
                raise UpdateError(journal["error"], "restore_conflict")
            journal["local_changes_restored"] = True
            journal["state"] = "CODE_UPDATED"
            journal.pop("error", None)
            _save_journal(journal)
            return {"success": True, "journal": journal}


manager = UpdateManager()
