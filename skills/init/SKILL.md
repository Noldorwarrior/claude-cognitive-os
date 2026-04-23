---
name: init
description: >-
  Инициализация когнитивного воркспейса с нуля. Создаёт структуру
  `cognitive_os/` (карточки 00-14, папки `projects/`, `archive/`,
  `_generated/`, `docs/`) по шаблонам из `templates/`. Запускается командами
  «инициализируй воркспейс», «создай когнитивное хранилище», «init cognitive
  os», «развернуть когнитивную карту». Используется ОДИН РАЗ при первом
  старте или при создании нового изолированного воркспейса.
---

# init — Инициализация когнитивного воркспейса

## Назначение

Создать структуру когнитивного воркспейса в папке, выбранной пользователем
(`/Users/.../Documents/Claude/cognitive_os/` по умолчанию), развернув
шаблоны карточек 00-14 из `${CLAUDE_PLUGIN_ROOT}/templates/`.

## Когда запускается

- Пользователь впервые активировал плагин.
- Пользователь просит «инициализируй воркспейс» / «init cognitive os» /
  «создай когнитивное хранилище».
- Создаётся второй изолированный воркспейс (например, для другого
  организационного контекста).

## Когда НЕ запускается

- Воркспейс уже существует (проверка наличия `00_index.md`) → предложить
  `migrate` или `status`.
- Пользователь просит миграцию из cognitive-os skill v1.0.1 → делегировать
  в [[migrate]].

## Workflow

### 1. Диалог с пользователем

Спросить через `AskUserQuestion`:

- **Путь воркспейса** (default: `<selected_folder>/cognitive_os/`).
- **Язык** (default: ru; из user-preferences rule #2).
- **Домены для калибровки** (multi-select из 8 заготовок в
  `11_confidence_scoring.md`).
- **Обсидиан-интеграция** (да/позже).

### 2. Проверка безопасности

- Если папка существует и не пуста — **СТОП**, предложить выбор:
  - Создать рядом (`cognitive_os_new/`).
  - Запустить [[migrate]] в режиме update.
  - Отменить.

### 3. Создание структуры

```
cognitive_os/
├── CLAUDE.md            (из templates/CLAUDE.md — bootstrap-файл, загружается в начале каждой сессии)
├── 00_index.md          (из templates/00_index.md)
├── 01_user_profile.md   (из templates/01_user_profile.md)
├── 02_patterns.md
├── 03_projects_registry.md
├── 04_meta_decisions.md
├── 05_global_glossary.md
├── 06_lessons_learned.md
├── 07_global_entities.md
├── 08_knowledge_maps.md
├── 09_working_mechanisms.md
├── 10_error_corrections.md    (dormant)
├── 11_confidence_scoring.md   (dormant)
├── 12_cross_project_graph.md  (dormant)
├── 13_self_reflection.md      (dormant)
├── 14_audit_log.md            (dormant)
├── projects/
├── archive/
├── _generated/
│   ├── graph.html       (placeholder)
│   ├── backlinks.md     (placeholder)
│   └── graph.mermaid    (placeholder)
└── docs/
    ├── verification_log.md
    ├── rate_limit_handling.md               (из templates — стаб v1.4.0)
    ├── verification_plugin_integration.md   (из templates — стаб v1.4.0)
    ├── obsidian_setup.md                    (из templates — стаб v1.4.0)
    └── advanced_confidence_calibration.md   (из templates — стаб v1.4.0)
```

**Важно**: `CLAUDE.md` в корне воркспейса — ключевой файл. Он содержит
навигационные маркеры (карта всех 15 карточек), reading ladder, контракт
работы с когнитивной памятью. Загружается автоматически в начале каждой
сессии Claude в этом воркспейсе.

### 4. Замена плейсхолдеров в шаблонах

- `{{DATE}}` → текущая дата (`YYYY-MM-DD`).
- Остальные плейсхолдеры остаются для заполнения по ходу работы.

### 5. Экспорт пути воркспейса

Добавить в `~/.zshrc` (или `~/.bashrc`):

```bash
export CLAUDE_WORKSPACE="/Users/.../cognitive_os"
```

Скрипты плагина читают путь из `$CLAUDE_WORKSPACE` (fallback — аргумент
`--workspace` у каждого CLI-скрипта). Этого достаточно для работы
хуков, `sync_check`, `render_graph`, `render_backlinks`.

### 6. Валидация после создания

- Проверить, что все 15 карточек созданы.
- Проверить frontmatter на корректность YAML.
- Запустить `sync_check.py` (если есть) для проверки порогов.

### 7. Отчёт пользователю

```
Воркспейс создан: /Users/.../cognitive_os/
Карточек развёрнуто: 15 (8 активных + 3 расширения + 4 служебные dormant).
Порогов зафиксировано: pattern=3, pattern_window_days=30, ... (см. 00_index).
Следующий шаг:
- Заполнить [[03_projects_registry]] действующими проектами.
- Или запустить [[migrate]] из cognitive-os v1.0.1.
```

## Обсидиан-интеграция (опционально)

Если пользователь выбрал «да»:
- Создать `cognitive_os/.obsidian/` с базовым конфигом (темы, горячие
  клавиши, включённый `graph view`).
- Указать на `examples/starter_workspace/.obsidian/` как референс.

## Верификация

Пресет **П13 «Аудитор»** — проверка структуры, полноты, корректности
frontmatter.

## Команды

| Команда | Действие |
|---|---|
| `инициализируй воркспейс` | Запустить init |
| `init cognitive os` | Алиас |
| `создай когнитивное хранилище` | Алиас |

## Интеграции

- [[productivity:memory-management]] — после init запускается first-time
  bootstrap memory (если установлен).
- [[migrate]] — delegation при обнаружении v1.0.1.
- [[status]] — запускается сразу после init для показа состояния.

## Частые ошибки

1. **Папка уже существует, но не проверили** → риск перезаписи.
   Защита: обязательная проверка в шаге 2.
2. **YAML frontmatter с опечатками** → ломает парсеры.
   Защита: валидация в шаге 6.
3. **`_generated/` пустые placeholders** не перерисованы автоматически.
   Защита: первая запись в любую карту триггерит [[graph]] и [[backlinks]].

## Связанные

- [[cognitive-os-core]] — ядро (SKILL.md в `skills/cognitive-os-core/`).
- [[migrate]], [[status]], [[graph]], [[backlinks]].
