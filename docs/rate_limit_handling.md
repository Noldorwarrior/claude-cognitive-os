# Rate limit handling

> **Статус:** 🚧 Заглушка. Будет развёрнута в v1.4.0.

## Назначение

Политика обработки rate limit'ов от Claude API и MCP-провайдеров внутри
когнитивного воркспейса: backoff, retry, очереди пакетных операций,
приоритизация критичных хуков над фоновыми.

## Планируемое содержание

- **Триггеры rate limit**: что именно возвращает 429 / `retry_after`.
- **Эскалация**: когда плагин переходит в degraded mode (только
  критичные хуки работают, детектор и async-fork паузятся).
- **Окна backoff**: экспоненциальные + джиттер, ограничения по хуку.
- **Визуализация в `14_audit_log.md`**: отдельная секция
  `rate_limit_events`.
- **Интеграция с `calibrate_thresholds`**: если rate limit сработал за
  последние 24 ч — откатить агрессивные пороги.
- **Пользовательские настройки**: `references/rate_limits.md` (новый
  файл с per-domain квотами).

## Связанные

- [[14_audit_log]] — журнал событий.
- [[calibrate]] — action-скилл для отката порогов.
- `scripts/run_detector.py` — основной потребитель API-квот в хуках.

## Текущее поведение (v1.3.3)

- Hooks используют timeout 5–15 сек.
- `@safe_main` ловит любое `Exception` и выдаёт структурированный JSON
  в stderr (exit 2). Rate limit в 429 проявляется как `OSError` →
  exit 1.
- Async-fork (`& disown`) не блокирует LLM — если graph/backlinks упал
  по квоте, Claude продолжает без них.

## Roadmap

- v1.4.0 — базовая политика backoff для `run_detector.py`.
- v1.5.0 — единый rate limit coordinator между хуками.
- v2.0.0 — cross-workspace throttling через shared `/tmp` state.
