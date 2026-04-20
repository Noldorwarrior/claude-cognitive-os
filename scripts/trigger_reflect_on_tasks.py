#!/usr/bin/env python3
"""
trigger_reflect_on_tasks.py — PostToolUse-хук для `TASKS.md`.

Срабатывает после Write/Edit на файл `TASKS.md` (из productivity:task-management).
Если в файле появилась новая отметка `[x]` (закрыта задача) с момента
последнего запуска — инжектит рекомендацию запустить [[reflect]] в следующий
ход LLM через `additionalContext`.

Дебаунс предотвращает спам при серии быстрых правок.

Протокол Claude Code PostToolUse:
- На stdin — JSON с полями `tool_name`, `tool_input.file_path`, `cwd`.
- На stdout (опционально) — JSON `{"additionalContext": "..."}`.
- Любой другой вывод в stderr / non-JSON stdout игнорируется.

Запуск (вызывается из hooks.json):
    python3 trigger_reflect_on_tasks.py --workspace /path --debounce 5

Выход: всегда 0, даже при ошибках чтения (хук не должен ломать сессию).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# Регекс закрытой задачи в TASKS.md (стиль productivity:task-management)
CHECKED_RE = re.compile(r"^\s*[-*]\s*\[x\]\s", re.MULTILINE | re.IGNORECASE)


def workspace_hash(workspace: str) -> str:
    """Короткий идентификатор воркспейса для namespace state-файлов в /tmp.

    Используется абсолютный путь → sha256 → hex[:12]. Гарантирует, что
    два разных воркспейса (или один перенесённый в другое место) не делят
    state-файлы и не триггерят ложные рекомендации.
    """
    try:
        abs_path = str(Path(workspace or ".").expanduser().resolve())
    except Exception:
        abs_path = workspace or "."
    return hashlib.sha256(abs_path.encode("utf-8")).hexdigest()[:12]


def state_paths(ws_hash: str) -> tuple[Path, Path, Path]:
    """(debounce, hash, checked_count) — файлы состояния для данного воркспейса.

    Файлы self-cleaning на ребуте (/tmp), namespace по ws_hash.
    """
    base = f"/tmp/cognitive_os_{ws_hash}"
    return (
        Path(f"{base}_debounce.txt"),
        Path(f"{base}_tasks_hash.txt"),
        Path(f"{base}_tasks_checked.txt"),
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", default=".", help="Путь к воркспейсу. Используется для namespace state-файлов в /tmp (разные воркспейсы не делят debounce/hash/counter).")
    p.add_argument("--debounce", type=int, default=5, help="Интервал дебаунса в секундах")
    return p.parse_args()


def read_hook_payload() -> dict:
    """Читает JSON payload с stdin. Возвращает пустой dict при любой ошибке."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def is_tasks_md(file_path: str) -> bool:
    """Проверяет, что путь указывает на TASKS.md (регистр имени файла не важен)."""
    if not file_path:
        return False
    try:
        return Path(file_path).name.upper() == "TASKS.MD"
    except Exception:
        return False


def debounce_ok(interval: int, debounce_file: Path) -> bool:
    """True если с прошлого срабатывания прошло ≥ interval секунд."""
    now = time.time()
    try:
        last = float(debounce_file.read_text().strip())
        if now - last < interval:
            return False
    except Exception:
        pass
    try:
        debounce_file.write_text(f"{now:.3f}\n")
    except Exception:
        pass
    return True


def count_checked(content: str) -> int:
    """Количество строк вида `- [x] ...` в TASKS.md."""
    return len(CHECKED_RE.findall(content))


def detect_new_check(file_path: str, checked_count_file: Path) -> tuple[bool, int, int]:
    """
    Сравнивает текущее количество `[x]` с сохранённым.
    Возвращает (появилась_новая_отметка, prev_count, current_count).
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False, 0, 0
    current = count_checked(content)
    prev = 0
    try:
        prev = int(checked_count_file.read_text().strip() or "0")
    except Exception:
        prev = 0
    try:
        checked_count_file.write_text(str(current))
    except Exception:
        pass
    return (current > prev, prev, current)


def hash_changed(file_path: str, hash_file: Path) -> bool:
    """True если хеш содержимого изменился с прошлого запуска."""
    try:
        content = Path(file_path).read_bytes()
    except Exception:
        return False
    current = hashlib.sha256(content).hexdigest()
    prev = ""
    try:
        prev = hash_file.read_text().strip()
    except Exception:
        prev = ""
    try:
        hash_file.write_text(current)
    except Exception:
        pass
    return current != prev


def emit_context(message: str) -> None:
    """Инжектит additionalContext в следующий ход LLM."""
    try:
        print(json.dumps({"additionalContext": message}, ensure_ascii=False))
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    payload = read_hook_payload()

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    # Быстрые фильтры (выход 0, тишина)
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0
    if not is_tasks_md(file_path):
        return 0

    # Namespace state-файлов по воркспейсу — разные проекты
    # не делят debounce/hash/counter, чтобы не ловить ложные триггеры.
    ws_hash = workspace_hash(args.workspace)
    debounce_file, hash_file, checked_count_file = state_paths(ws_hash)

    if not hash_changed(file_path, hash_file):
        # Файл не поменялся (холостое Edit) — молчим.
        return 0
    if not debounce_ok(args.debounce, debounce_file):
        return 0

    new_check, prev, cur = detect_new_check(file_path, checked_count_file)
    if new_check:
        emit_context(
            "В `TASKS.md` появилась новая отметка `[x]` "
            f"(было {prev}, стало {cur} закрытых задач). "
            "Рекомендуется запустить [[reflect]] для самоаудита по 8 осям "
            "и фиксации уроков в `06_lessons_learned.md`. "
            "Если задача была простой — можно пропустить."
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Хук не должен ломать сессию ни при каких обстоятельствах.
        sys.exit(0)
