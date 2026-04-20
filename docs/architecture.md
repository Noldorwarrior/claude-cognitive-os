# Архитектура claude-cognitive-os v1.3

## Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│  Пользователь                                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Основной агент Claude (orchestrator)                           │
│  - читает детектор сигналов                                      │
│  - применяет скиллы по триггерам                                 │
│  - взаимодействует с пользователем (AskUserQuestion)             │
└─────────────────────────────────────────────────────────────────┘
          │                    │                     │
          ▼                    ▼                     ▼
┌──────────────┐     ┌───────────────────┐   ┌──────────────────┐
│ Action-скил- │     │  Reference-скиллы │   │  Субагенты       │
│ лы (10)      │◄────│  (2)              │   │  (3)             │
│              │     │                   │   │                  │
│ init         │     │ cognitive-os-core │   │ cog-archivist    │
│ migrate      │     │ cognitive-os-graph│   │ cog-detector     │
│ status       │     │ cognitive-os-calib│   │ cog-verifier     │
│ graph        │     └───────────────────┘   └──────────────────┘
│ backlinks    │                │                     │
│ reflect      │                │                     │
│ calibrate    │                ▼                     ▼
│ archive      │     ┌──────────────────────────────────────────┐
│ patterns     │     │  Python scripts (scripts/)               │
│ audit        │     │                                          │
└──────────────┘     │  render_graph.py                         │
          │          │  render_backlinks.py                     │
          │          │  render_mermaid.py                       │
          │          │  calibrate_thresholds.py                 │
          │          │  extract_principles.py                   │
          │          │  sync_check.py                           │
          │          │  paginate_projects.py                    │
          │          │  paginate_patterns.py                    │
          │          │  audit_contradictions.py                 │
          │          │  run_detector.py                         │
          │          └──────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Когнитивный воркспейс (cognitive-os/)                          │
│                                                                  │
│  00_index.md            08_knowledge_maps.md                    │
│  01_user_profile.md     09_working_mechanisms.md                │
│  02_patterns.md         10_error_corrections.md                 │
│  03_projects_registry.md 11_confidence_scoring.md               │
│  04_meta_decisions.md   12_cross_project_graph.md               │
│  05_global_glossary.md  13_self_reflection.md                   │
│  06_lessons_learned.md  14_audit_log.md                         │
│  07_global_entities.md                                           │
│                                                                  │
│  _generated/            archive/             projects_pages/    │
│  - graph.html           - 02_patterns/       (при >100)         │
│  - graph.mermaid        - .backup/           patterns_groups/   │
│  - backlinks.md                              (при >200)         │
│  - detector_signals.md                                          │
│  - sync_report.md                                               │
│  - calibration_report.md                                        │
│  - principle_candidates.md                                      │
│  - contradictions_report.md                                     │
└─────────────────────────────────────────────────────────────────┘
          │                              │
          │                              │
          ▼                              ▼
┌───────────────────┐          ┌─────────────────────────────────┐
│ hooks/hooks.json  │          │  Внешние плагины (optional)     │
│                   │          │                                  │
│ post-write:       │          │ - verification (П1-П14)         │
│  render_graph     │          │ - govdoc-analytics              │
│  render_backlinks │          │   (self-reflection)             │
│  run_detector     │          │                                  │
│                   │          └─────────────────────────────────┘
│ scheduled:        │
│  sync_check       │
│  full detector    │
└───────────────────┘
```

## Слои

### 1. Слой данных (воркспейс)

15 карточек `0N_*.md` и `1N_*.md` — «живые» Markdown-файлы со структурой
wikilinks. Обсидиан-совместимо. Все сущности имеют ID с префиксом
(`pat-`, `wm-`, `km-`, ...). Wikilinks вида `[[pat-001]]` или
`[[02_patterns#pat-001]]`.

### 2. Слой исполнителей (scripts/)

Python-скрипты на stdlib (argparse, re, dataclasses, json, pathlib).
Без внешних зависимостей, кроме опционального vis-network.js через CDN
для интерактивной HTML-визуализации.

### 3. Слой скиллов

**Action-скиллы (10)** — триггерятся русскими фразами, выполняют
пользовательские действия.

**Reference-скиллы (3)** — загружаются action-скиллами для справочной
информации и методологии:
- `cognitive-os-core` — правила, пороги, ID-конвенции.
- `cognitive-os-graph` — методология визуализации.
- `cognitive-os-calibration` — методология self-learning.

### 4. Слой субагентов

**Не вызываются пользователем напрямую:**
- `cog-archivist` — исполнитель архивных операций.
- `cog-detector` — фоновый детектор сигналов (через hooks).
- `cog-verifier` — верификатор пресетов (П5/П12/П13/П14).

Каждый субагент имеет собственный контекст — не засоряет основной.

### 5. Слой хуков

`hooks/hooks.json` описывает post-write и scheduled триггеры с
`debounce_seconds` 3-5. `mtime-check` внутри скриптов обеспечивает
идемпотентность.

## Жизненный цикл воркспейса

### Bootstrap

1. `[[init]]` — пользователь создаёт новый воркспейс.
2. Создаются 15 карточек из шаблонов.
3. Регистрация в `~/.claude/cognitive-os-workspaces.json`.

### Ежедневная работа

1. Пользователь пишет / редактирует карточки.
2. `hooks.json` триггерит `render_graph` + `render_backlinks` +
   `run_detector`.
3. `_generated/` обновляется автоматически.
4. При обнаружении сигналов детектор пишет в `detector_signals.md`.

### Еженедельное

1. Пользователь запрашивает `[[reflect]]` (или автоматически).
2. Создаётся `sr-NNN`, обновляется `11_confidence_scoring`.
3. Извлекаются уроки в `06_lessons_learned`.

### Ежемесячное

1. `[[calibrate]]` — анализ точности прогнозов.
2. `extract_principles.py` — кандидаты в md-NNN.
3. `[[patterns]]` promotion — wm-NNN → md-NNN.

### Ежеквартальное

1. `[[audit]] full` — глубокая проверка.
2. `[[archive]]` холодных записей.
3. `sync_check.py --strict` — валидация.

## Масштабирование

| Размер | Стратегия |
|---|---|
| < 100 записей | Базовая, 15 карточек |
| 100-500 | Базовая, пагинация не нужна |
| 500-1000 | Auto-пагинация projects при > 100 |
| 1000-3000 | + auto-пагинация patterns при > 200 |
| > 3000 | Разбиение воркспейса на несколько (domain-splits) |

## Взаимодействие с внешними плагинами

### `verification` plugin (приоритетный)

Субагент `cog-verifier` делегирует в `verification:verify` с указанием
пресета (П5/П12/П13/П14). Если плагин недоступен — внутренний fallback
(упрощённые проверки).

### `govdoc-analytics:self-reflection` (приоритетный)

Скилл `[[reflect]]` делегирует туда. Fallback — internal_8axis_scoring.

Автономная работа без этих плагинов **полностью поддерживается** — это
принципиальное требование архитектуры.

## Обсидиан-совместимость

- Все файлы `.md` с YAML frontmatter.
- Wikilinks `[[target]]` и `[[target#anchor]]`.
- Папки как теги / группы (`projects/`, `archive/`).
- `.obsidian/` в starter_workspace содержит предзаполненный workspace.json.

## Безопасность

### Принципы

1. **Всегда бэкап перед записью** (в `archive/.backup/{{TIMESTAMP}}/`).
2. **Dry-run поддерживается везде**, где возможна запись.
3. **П14 верификация** после любой массовой правки.
4. **Хуки пишут только в `_generated/`**, никогда в продовые карточки.
5. **Восстановление** из бэкапа при провале верификации.

### Отсутствующие опасности

- Внешних сетевых запросов нет (кроме опционального vis-network CDN).
- Никакого outbound — воркспейс локальный.
- Все API-интеграции через MCP опциональны.

## Связанные документы

- [[quick_start]] — быстрый старт.
- [[migration_guide]] — миграция с v1.0.1.
- [[thresholds_reference]] — все пороги.
- [[presets_reference]] — пресеты верификации.
