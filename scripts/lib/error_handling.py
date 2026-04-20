"""
error_handling — централизованная обработка ошибок для скриптов плагина.

Декоратор ``@safe_main`` оборачивает точку входа скрипта (``main()``)
и гарантирует:

1. Любое исключение логируется в structured-формате (JSON) в stderr.
2. Скрипт всегда завершается явным exit-кодом:
   * 0 — успех
   * 1 — обработанная ошибка (например, файл не найден)
   * 2 — непойманное исключение
3. Hooks на стороне Claude Code/Cowork получают предсказуемый контракт:
   ошибка одного скрипта не валит всю цепочку PostToolUse.

Использование
-------------

```python
# scripts/render_graph.py
from lib.error_handling import safe_main

@safe_main
def main() -> int:
    # ... вся логика скрипта ...
    return 0

if __name__ == "__main__":
    main()
```

Совместимо с ``argparse``-based скриптами — декоратор не меняет сигнатуру.
Если ``main()`` возвращает int — он используется как exit-код.
Если ничего не возвращает — exit-код 0.

Введено в v1.3.3 (2026-04-21).
"""

from __future__ import annotations

import functools
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Callable


def _log_structured(level: str, event: str, **fields: Any) -> None:
    """Записывает JSON-строку в stderr. Безопасно для non-serializable типов."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
    }
    for key, value in fields.items():
        try:
            json.dumps(value)
            record[key] = value
        except (TypeError, ValueError):
            record[key] = repr(value)
    try:
        print(json.dumps(record, ensure_ascii=False), file=sys.stderr)
    except Exception:  # pragma: no cover — защита от совсем странных окружений
        sys.stderr.write(f"[{level}] {event}\n")


def safe_main(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Оборачивает точку входа скрипта.

    Поведение:
    * Ловит ``KeyboardInterrupt`` → exit 130 (стандарт Unix).
    * Ловит ``SystemExit`` → пропускает (argparse использует его сам).
    * Ловит ``FileNotFoundError``, ``PermissionError``, ``OSError`` →
      structured-лог уровня ``ERROR`` + exit 1.
    * Ловит любое другое ``Exception`` → structured-лог уровня ``CRITICAL``
      с traceback + exit 2.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        script_name = getattr(func, "__module__", "unknown")
        try:
            result = func(*args, **kwargs)
        except KeyboardInterrupt:
            _log_structured(
                "WARNING", "interrupted", script=script_name
            )
            sys.exit(130)
        except SystemExit:
            # argparse / sys.exit() — пропускаем без оборачивания
            raise
        except (FileNotFoundError, PermissionError, OSError) as exc:
            _log_structured(
                "ERROR",
                "io_error",
                script=script_name,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001 — осознанный catch-all
            _log_structured(
                "CRITICAL",
                "unhandled_exception",
                script=script_name,
                error_type=type(exc).__name__,
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            sys.exit(2)

        # Успешный путь
        if isinstance(result, int):
            sys.exit(result)
        return result

    return wrapper


__all__ = ["safe_main"]
