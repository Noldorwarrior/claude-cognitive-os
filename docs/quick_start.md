# Быстрый старт claude-cognitive-os v1.3

## Установка

```bash
# Клонируйте или скопируйте плагин в папку Claude
cp -r claude-cognitive-os ~/.claude/plugins/

# Или через marketplace
claude plugin install claude-cognitive-os
```

## Первый воркспейс

### Шаг 1: Создание

В Claude скажите:

> создай когнитивный воркспейс

Или:

> init cognitive os в /path/to/my-workspace

Скилл [[init]] задаст несколько вопросов:
- Путь к воркспейсу (по умолчанию `~/Documents/cognitive-os/`).
- Имя воркспейса (для UI).
- Опциональная Obsidian-интеграция (создать `.obsidian/`).

Будут созданы 15 стартовых карточек с шаблонным содержимым:

```
my-workspace/
├── 00_index.md
├── 01_user_profile.md
├── 02_patterns.md
├── 03_projects_registry.md
├── 04_meta_decisions.md
├── 05_global_glossary.md
├── 06_lessons_learned.md
├── 07_global_entities.md
├── 08_knowledge_maps.md
├── 09_working_mechanisms.md
├── 10_error_corrections.md
├── 11_confidence_scoring.md
├── 12_cross_project_graph.md
├── 13_self_reflection.md
├── 14_audit_log.md
├── _generated/
│   └── (автоматически генерируемые файлы)
└── archive/
    └── (пусто на старте)
```

### Шаг 2: Первая запись

Откройте `01_user_profile.md` и заполните:
- Имя / роль.
- Приоритетные домены.
- Предпочтения в коммуникации.

Сохраните. Хуки автоматически пересоберут граф и backlinks.

### Шаг 3: Первый проект

Скажите:

> добавь проект «Разработка плагина X»

Или вручную добавьте в `03_projects_registry.md`:

```markdown
## proj-001 — Разработка плагина X

- domain: tooling
- entities: [[ent-001]]
- status: active
- started: 2026-04-20

**Описание:** ...
```

### Шаг 4: Рефлексия после задачи

После крупной задачи скажите:

> проведи самоанализ

Скилл [[reflect]] создаст `sr-NNN` в `13_self_reflection.md` с оценкой
по 8 осям и обновит `11_confidence_scoring`.

## Частые команды

| Фраза | Что делает |
|---|---|
| `покажи статус` | [[status]] — обзор воркспейса |
| `покажи граф` | [[graph]] — HTML визуализация |
| `найди ссылки на pat-003` | [[backlinks]] `--id pat-003` |
| `что детектор видит?` | Показать `detector_signals.md` |
| `проведи аудит` | [[audit]] — полная проверка |
| `откалибруй пороги` | [[calibrate]] — анализ уверенности |
| `архивируй холодные паттерны` | [[archive]] — очистка |
| `покажи паттерн-кандидаты` | [[patterns]] — промоушен |

## Миграция с v1.0.1

Если у вас есть старый воркспейс из скилла `cognitive-os v1.0.1`:

> мигрируй воркспейс из /path/to/old

Скилл [[migrate]] сделает бэкап, разобьёт 18 карт в 15 новых, проверит
целостность и запустит П14 верификацию.

Подробнее — [[migration_guide]].

## Obsidian-интеграция

Папка воркспейса сразу открывается в Obsidian:
1. File → Open vault → выбрать папку.
2. Wikilinks, граф, backlinks работают нативно.
3. HTML-граф из `_generated/graph.html` открывается в браузере.

В поставке `examples/starter_workspace/.obsidian/` есть предзаполненный
workspace.json.

## Рекомендуемый недельный цикл

**Понедельник:** запланируйте задачи, добавьте новые проекты.

**Ежедневно:** записывайте наблюдения в 02_patterns (observations).

**Пятница:**
- `покажи статус` — что накопилось.
- `проведи самоанализ` — недельный sr-NNN.

**Первое число месяца:**
- `откалибруй пороги` — raport по доменам.
- `покажи паттерн-кандидаты` — ревью новых паттернов.

**Первый день квартала:**
- `проведи аудит` — полная проверка.
- `архивируй холодные` — очистка.

## Что делать дальше

- Прочтите [[architecture]] для понимания внутреннего устройства.
- Прочтите [[thresholds_reference]] для настройки порогов.
- Изучите [[presets_reference]] для понимания верификации.

## Решение проблем

### «Граф не рисуется»

```bash
# Запустите вручную с подробностями
python3 scripts/render_graph.py --workspace /path/to/ws
```

Проверьте, что `vis-network` CDN доступен. Если нет — используйте
mermaid-версию: `graph.mermaid`.

### «Хуки не срабатывают»

Проверьте, что плагин активирован:
```bash
claude plugin list
```

И что `hooks/hooks.json` прочитан. Ручной запуск хука:
```bash
python3 scripts/render_graph.py --workspace $CLAUDE_WORKSPACE
```

### «Детектор даёт много ложных сигналов»

Повысьте пороги в `references/thresholds.md`:
- `pattern`: 3 → 5
- `cluster_min_projects`: 3 → 5

### «Воркспейс стал медленным»

Если > 500 проектов / > 200 паттернов — запустите пагинацию:
```bash
python3 scripts/paginate_projects.py --workspace .
python3 scripts/paginate_patterns.py --workspace . --strategy by-domain
```
