# CHANGELOG

Все значимые изменения фиксируются в этом файле.

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: [SemVer](https://semver.org/lang/ru/).

## [1.3.3] — 2026-04-21

### Added

- **Универсальная обработка ошибок (`scripts/lib/error_handling.py`)**: декоратор `@safe_main` с структурированным JSON-логированием в stderr. Ловит `KeyboardInterrupt` (exit 130), `SystemExit` (пропускает), `OSError`/`IOError` (exit 1), любое `Exception` (exit 2 + traceback). Обёрнуто 10 скриптов: `render_graph.py`, `render_backlinks.py`, `run_detector.py`, `calibrate_thresholds.py`, `extract_principles.py`, `paginate_patterns.py`, `paginate_projects.py`, `audit_contradictions.py`, `render_mermaid.py`, `sync_check.py`. Скрипт `trigger_reflect_on_tasks.py` намеренно исключён — у PostToolUse-хука собственный контракт (exit 0 даже при ошибке).
- **Документация-заглушки (`docs/`)**: `rate_limit_handling.md`, `verification_plugin_integration.md`, `obsidian_setup.md`, `advanced_confidence_calibration.md` — стабы для будущего расширения. Создаются при `init` воркспейса.
- **Шаблон `templates/CLAUDE.md`**: bootstrap-файл для воркспейса, загружаемый в начале каждой сессии. Содержит навигационные маркеры, краткий обзор 15 карточек и reading ladder.

### Changed

- **Hooks async-fork для graph + backlinks**: команды в `hooks/hooks.json` теперь запускаются через `nohup ... & disown` в фоне (timeout 5 сек вместо 30/20). Позволяет Claude продолжать работу, не дожидаясь окончания рендера графа и backlinks. Остальные хуки (`run_detector.py`, `trigger_reflect_on_tasks.py`) остались синхронными — им нужен синхронный `additionalContext` в следующий ход LLM.
- **cog-verifier model: sonnet → opus**: верификатор П5 «Максимум» и критичных документов теперь использует Claude Opus 4.6 вместо Sonnet 4.6 для более глубокой проверки. `cog-detector` и `cog-archivist` остались на Sonnet 4.6 (фоновые read-only / механистичные операции).
- **init SKILL.md**: шаг 3 дополнен созданием `CLAUDE.md` в корне воркспейса из `templates/CLAUDE.md`.
- **README.md**: удалена строка `**Версия:** v1.3.x` (первичный источник — `.claude-plugin/plugin.json`, см. lesson-006 в memory). Добавлен раздел «Обновление» с инструкцией и ссылкой на CHANGELOG.

### Rationale

Async-fork снижает латентность на 15–35 сек на каждый Write/Edit, что особенно критично при пакетных правках. `@safe_main` даёт предсказуемое поведение скриптов (структурированные ошибки вместо немого падения), упрощает дебаг хуков. Opus 4.7 на cog-verifier оправдан только для критичных проверок (см. бенчмарки HRMAH/GPQA).

## [1.3.2] — 2026-04-21

### Added

- **TASKS.md post-edit hook** (`scripts/trigger_reflect_on_tasks.py`): реальный PostToolUse-хук на Write/Edit по `TASKS.md`. Парсит количество закрытых пунктов (`- [x]`), при приросте инжектит `additionalContext` с рекомендацией запустить [[reflect]]. Дебаунс 5 сек, проверка hash для защиты от холостых Edit. Зарегистрирован в `hooks/hooks.json` как четвёртый хук. Заменяет описание «хук на завершение задачи» в `skills/reflect/SKILL.md` реальной реализацией.

### Changed

- **Workspace-scoped state в `/tmp`**: state-файлы `trigger_reflect_on_tasks.py` (debounce, hash, checked-counter) теперь namespace'ятся по SHA256[:12] абсолютного пути воркспейса. Два параллельных воркспейса (разные `${CLAUDE_WORKSPACE}`) больше не делят state и не триггерят ложные рекомендации у соседа. Self-healing на ребуте (файлы остаются в `/tmp`).
- **Динамические пороги в `run_detector.py`**: хардкод `THRESH` заменён на `THRESH_DEFAULTS` + `load_thresholds()`. Фактические значения подтягиваются из `<workspace>/references/thresholds.md` или `<workspace>/docs/thresholds_reference.md` (тот же формат markdown-таблицы, что читает `sync_check.py`). Неизвестные ключи игнорируются. Защищает от расхождения «пороги в `00_index` ≠ пороги в детекторе». Все `find_*`-функции теперь принимают `thresh` аргументом — глобал устранён.

### Housekeeping

- Артефакт `scripts/__pycache__/` (появляется при локальном `python3 -c`/`py_compile` во время разработки) не должен попадать в пакет плагина. Рекомендация: добавить `__pycache__/` и `*.pyc` в корневой `.gitignore` при первом коммите истории плагина в VCS.

## [1.3.1] — 2026-04-20

### Fixed

- **Hook spam**: добавлен no-op флаг `--if-changed` в argparse скриптов `render_graph.py`, `render_backlinks.py`, `run_detector.py`. Флаг передаётся из `hooks/hooks.json`, но скрипты раньше о нём не знали и падали с `unrecognized arguments`. Ошибки не блокировали запись файлов, но спамили вывод на каждом Write/Edit. Скрипты идемпотентны (проверка mtime внутри), поэтому флаг можно безопасно игнорировать.

## [1.3.0] — 2026-04-20

### Контекст миграции

Эта версия — **переход из skill в полноценный плагин**. Предыдущая версия — skill `cognitive-os v1.0.1` (см. историю ниже). Плагин включает все функции skill и добавляет визуализацию, автокалибровку, self-learning и интеграции.

### Added

- **Визуальный граф** связей на vis-network (интерактивный HTML с фильтрами по типу сущности)
- **Backlinks** для AI-чтения (`_generated/backlinks.md`)
- **Mermaid-граф** как fallback для быстрого обзора
- **3 knowledge-скилла:** cognitive-os-core, cognitive-os-graph, cognitive-os-calibration
- **10 action-скиллов:** init, migrate, status, graph, backlinks, reflect, calibrate, archive, patterns, audit
- **3 субагента:** cog-archivist (архивация), cog-detector (детекция сигналов), cog-verifier (делегирование в verification plugin)
- **Hooks** (`hooks/hooks.json`) с debounce 3-5 сек и mtime-check идемпотентностью — автопересборка графа/backlinks, инкрементальная детекция
- **Автокалибровка порогов** (`calibrate_thresholds.py`) на базе накопленных данных
- **Автоизвлечение принципов** (`extract_principles.py`) из 3+ уроков
- **Детектор сигналов** (`run_detector.py`) — pattern_candidate / cluster_candidate / systemic_error / conflict_suspect / cold_candidate
- **Аудит противоречий** (`audit_contradictions.py`) для поиска конфликтов во всём vault'е
- **Пагинация** для масштаба 100+ проектов и 50+ паттернов (by-domain / by-tag / by-range)
- **Sync-check** (`sync_check.py`) между `02_patterns.md` и SKILL.md
- **Reading ladder** с обзорным уровнем
- **Starter workspace** — 15 карточек + `.obsidian/workspace.json` + `core-plugins.json` + README
- **Справочная документация:** `docs/thresholds_reference.md` и `docs/presets_reference.md`
- **15 шаблонов карточек** 00_index → 14_audit_log с YAML frontmatter и `[[wikilinks]]`
- **Integration docs** — три сценария (только плагин / только Obsidian / комбо)
- **Delegation pattern:** внешний `verification:verify` как основной путь + внутренний fallback при отсутствии плагина

### Changed

- Формат: `skill` → `plugin` со структурой `.claude-plugin/plugin.json`
- Команды: из inline-инструкций → отдельные action-скиллы `skills/<name>/SKILL.md`
- Пути: все хардкоды заменены на `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_WORKSPACE}`, `${CLAUDE_CHANGED_FILES}`
- Шаблон `14_task_queue.md` → `14_audit_log.md` (журнал системных событий)

### Deferred к v2.0.0

- Мультиагентная координация (3+ параллельных cog-агентов с shared memory)
- Многопользовательский режим (shared vault с конфликт-резолюшеном)
- Cloud sync (опционально)

### Стадии разработки

| Этап | Описание | Статус |
|---|---|---|
| 0 | Чтение skill `create-cowork-plugin` | ✅ |
| 1 | Скелет + манифест + README + CHANGELOG | ✅ |
| 2 | Миграция `cognitive-os-core` из v1.0.1 SKILL.md | ✅ |
| 3 | Миграция 15 шаблонов карточек | ✅ |
| 4 | 10 action-скиллов | ✅ |
| 5 | Визуализация (graph/backlinks/mermaid + скилл) | ✅ |
| 6 | 3 субагента + hooks/hooks.json | ✅ |
| 7 | Self-learning (3 скрипта + скилл calibration) | ✅ |
| 8 | (Отложен на v2.0 — мультиагентность) | ⏸ |
| 9 | Масштабируемость + docs + examples + Obsidian-конфиг | ✅ |
| 10 | Финальная верификация П5+П13+П14 + упаковка .plugin | ✅ |

---

## [1.0.1] cognitive-os skill — 2026-04 (предыдущая итерация)

### Fixed (4 минора после верификации П5)

- Синхронизация порогов `02_patterns.md` ↔ `SKILL.md` через sync-comments
- Добавлены `total_maps: 4`, `starter_ids: [km-001..004]` в `08_knowledge_maps.md`
- Добавлены `total_mechanisms: 7`, `starter_ids: [wm-001..007]` в `09_working_mechanisms.md`
- Фиксация `systemic_threshold: 3` в `10_error_corrections.md`
- Централизованный `extraction_logic.md` с единым блоком параметров
- Обновлён `roadmap.md` с планами v1.1.0/v1.2.0/v2.0.0
- Обновлён `verification_p5_log.md` с фиксацией патчей

### Added (ранее)

- 15 шаблонов карточек (00-14)
- Механизмы извлечения паттернов/ошибок
- Reading ladder 0..2
- `extraction_logic.md` с параметрами экстракции
- Интеграция с `verification` plugin (П1-П14)

---

## [1.0.0] cognitive-os skill — 2026-04

### Added

- Первая стабильная версия skill
- Ядро: SKILL.md с frontmatter (thresholds, fallbacks, reading_ladder)
- Шаблоны 00-07 (базовое ядро)
- Шаблоны 08-10 (расширение: knowledge_maps, working_mechanisms, error_corrections)
- Шаблоны 11-14 (служебные: sessions, checkpoints, open_questions, task_queue)
- Верификация П5 (32 механизма)
- Рефакторинг под архитектуру «ядро + адаптивные»
