# Link Conventions — соглашения по wikilinks в когнитивном воркспейсе

**Версия:** 1.3.8
**Дата:** 2026-04-23
**Область:** все markdown-файлы vault (`cognitive_os/`), documentation (`docs/`) и carry-over материалы (`projects/*/carry-over/`).

---

## 1. Зачем этот документ

В воркспейсе три параллельные системы сущностей ссылаются друг на друга:

1. **Vault** — карточки 00-14 и записи с ID (`pat-001`, `wm-003`, `ent-012`...).
2. **Плагин** — skills плагина `claude-cognitive-os` (`migrate`, `reflect`, `graph`, `audit`, ...) и других плагинов (`govdoc-analytics:verify`, `verification:verify-plan`).
3. **Agent-memory** — файлы памяти пользователя (`feedback_*`, `reference_*`, `user_*`).
4. **Carry-over** — рабочие plan-файлы в `projects/*/carry-over/`.

Все они адресуются через один синтаксис `[[target]]`, но `link_classifier.py` разносит их по классам по разным правилам. Этот документ — единственный источник истины по правилам.

## 2. Шесть классов ссылок

`link_classifier.classify_target` возвращает ровно одно из шести значений:

| Класс | Пример | Распознавание |
|---|---|---|
| `vault` | `[[pat-001]]`, `[[02_patterns]]`, `[[audit-012]]` | `VAULT_ID_PATTERN` (prefix-NNN) или `CARD_NAMES` (00_index..14_audit_log), **при условии что** target присутствует в vault_ids |
| `plugin` | `[[claude-cognitive-os:migrate]]`, `[[govdoc-analytics:verify]]` | `PLUGIN_LINK_PATTERN = ^[\w.\-]+:[\w.\-]+$` — namespace:skill |
| `agent` | `[[cog-verifier]]`, `[[init]]` | short-name из `ALLOWED_AGENTS` (см. ниже) |
| `carry_over` | `[[task-07-closure-gate-plan]]` | имя файла (без `.md`) из `projects/*/carry-over/` |
| `memory` | `[[feedback_deadline_always_asap]]` | имя файла (без `.md`) из agent-memory-директории |
| `dangling` | всё остальное | ничего из вышеперечисленного не подошло — требует внимания, ломает `sync_check` |

**Порядок проверок (важно):**
`plugin` → `agent` → `vault` → `carry_over` → `memory` → `dangling`.

`plugin` проверяется первым: namespace-сегмент в теории может совпасть с vault-ID или именем карточки, и двоеточие — единственный надёжный дискриминатор. `agent` раньше `carry_over`/`memory`: allow-list критичнее совпадений по имени файла.

## 3. ALLOWED_AGENTS — 6 имён, почему именно они

```python
ALLOWED_AGENTS: frozenset[str] = frozenset({
    "cog-verifier",
    "cog-archivist",
    "cog-detector",
    "init",
    "verification",
    "consolidate-memory",
})
```

Это **закрытый allow-list** для коротких (без namespace'а) ссылок. Состав подобран по двум критериям:

1. **Субагенты плагина `claude-cognitive-os`** (`cog-verifier`, `cog-archivist`, `cog-detector`) — объявлены в `.claude-plugin/plugin.json` как агенты, запускаются субагентным механизмом, а не как команды. Писать `[[claude-cognitive-os:cog-verifier]]` — можно, но избыточно: агент по имени уникален во всём плагине и не пересекается со skill-именами.

2. **Системные skills, объявленные вне namespace'а плагина** (`init`, `verification`, `consolidate-memory`) — legacy от эпохи до строгого namespace'инга (v1.3.x). Оставлены для обратной совместимости: до 1.3.x существующие vault-документы ссылались на них короткими именами; переименование сломало бы 100+ ссылок.

**Список закрытый.** При добавлении нового субагента/системного скилла **обновляется одновременно**:
- `scripts/link_classifier.py:ALLOWED_AGENTS`
- `docs/link-conventions.md` (этот файл, таблица ниже)
- `CHANGELOG.md` — секция Changed, с rationale.

### Текущий реестр ALLOWED_AGENTS (v1.3.8)

| Short-name | Тип | Полная форма | Rationale |
|---|---|---|---|
| `cog-verifier` | subagent | — (агент, не skill) | Plugin subagent |
| `cog-archivist` | subagent | — | Plugin subagent |
| `cog-detector` | subagent | — | Plugin subagent |
| `init` | skill | `claude-cognitive-os:init` | Legacy short-form; 50+ ссылок в vault |
| `verification` | plugin | `verification:verify` | Namespace совпадает с именем, legacy |
| `consolidate-memory` | skill (anthropic-skills) | `anthropic-skills:consolidate-memory` | Legacy short-form |

## 4. Skills плагина `claude-cognitive-os` — полный namespace обязателен

**НЕ входят в ALLOWED_AGENTS** (т.е. **требуют полный namespace `claude-cognitive-os:`**):

- `archive`
- `audit`
- `backlinks`
- `calibrate`
- `cognitive-os-calibration` (reference-скилл)
- `cognitive-os-core` (reference-скилл)
- `cognitive-os-graph` (reference-скилл)
- `graph`
- `migrate`
- `patterns`
- `reflect`
- `status`

**Правильные примеры:**

```markdown
[[claude-cognitive-os:migrate]]      ← PLUGIN
[[claude-cognitive-os:reflect]]      ← PLUGIN
[[claude-cognitive-os:cognitive-os-graph#Производительность]] ← PLUGIN + anchor
```

**Неправильные (будут классифицированы как `dangling`):**

```markdown
[[migrate]]   ← dangling: не в ALLOWED_AGENTS и не plugin:skill
[[reflect]]   ← dangling: аналогично
[[graph]]     ← dangling: аналогично
```

## 5. Vault ID и карточки

| Префикс | Карточка | Пример |
|---|---|---|
| `pat-NNN` | 02_patterns | `[[pat-009]]` |
| `wm-NNN` | 09_working_mechanisms | `[[wm-003]]` |
| `ec-NNN` | 10_error_corrections | `[[ec-006]]` |
| `km-NNN` | 08_knowledge_maps | `[[km-002]]` |
| `md-NNN` | 04_meta_decisions | `[[md-014]]` |
| `term-NNN` | 05_global_glossary | `[[term-007]]` |
| `ent-NNN` | 07_global_entities | `[[ent-020]]` |
| `proj-NNN` | 03_projects_registry | `[[proj-014]]` |
| `lesson-NNN` | 06_lessons_learned | `[[lesson-003]]` |
| `sr-NNN` | 13_self_reflection | `[[sr-042]]` |
| `audit-NNN` | 14_audit_log | `[[audit-005]]` |
| `domain-NNN` | 05_global_glossary (домены) | `[[domain-013]]` |
| `cluster-NNN` | 12_cross_project_graph | `[[cluster-002]]` |

Минимум 3 цифры (паттерн `-\d{3,}`). Anchor после `#` допускается: `[[pat-009#Эшелонированный]]`.

## 6. Carry-over — по stem файла

Файлы в `projects/*/carry-over/*.md` индексируются по имени без `.md`:

```
projects/proj-014/carry-over/task-07-closure-gate-plan.md
→ [[task-07-closure-gate-plan]]
```

Уникальность имён между проектами **не гарантируется** — при коллизии индексируется первый найденный (детерминированно по `rglob`). При планировании имён файлов carry-over избегать общих слов (`plan.md`, `handoff.md`); использовать `task-NN-<slug>-plan.md`.

## 7. Memory — по stem файла в auto-memory-директории

Файлы в `~/Library/Application Support/Claude/local-agent-mode-sessions/<session>/spaces/<space>/memory/*.md` индексируются аналогично:

```
memory/feedback_deadline_always_asap.md
→ [[feedback_deadline_always_asap]]
```

При запуске скриптов из sandbox — `link_classifier.find_default_memory_dir()` также проверяет `/sessions/*/mnt/.auto-memory` (монтируется Cowork).

## 8. Типичные ошибки

### Ошибка 1: skill плагина без namespace'а

```markdown
запустить [[reflect]] skill
```

**Правильно:**

```markdown
запустить [[claude-cognitive-os:reflect]] skill
```

**Почему:** `reflect` не в `ALLOWED_AGENTS` и не содержит двоеточия. Классификатор → `dangling`.

### Ошибка 2: карточка с опечаткой

```markdown
см. [[02_pattrns]]   ← опечатка
```

**Правильно:** `[[02_patterns]]`.

### Ошибка 3: vault-ID с 1-2 цифрами

```markdown
см. [[pat-1]]   ← dangling: <3 цифр
```

**Правильно:** `[[pat-001]]`. Минимум 3 цифры — по историческому соглашению для сортировки.

### Ошибка 4: wikilink внутри `inline code`

```markdown
Пример: `[[pat-009]]` — это ссылка.
```

Это **не ошибка**: эшелонированный препроцессинг `strip_backticked` (см. pat-009) снимает inline code и fenced blocks до классификации. Но подряд два backtick'а без закрытия — да, сломают парсер.

## 9. Валидация

Два скрипта используют `link_classifier`:

- **`scripts/sync_check.py`** — `sync_check.ensure_all_links_resolve()` вызывает `classify_target` и ломает коммит при `dangling`. Запускается вручную (`skill status`) или предкоммит-хуком.
- **`scripts/render_backlinks.py`** — группирует все ссылки по 6 классам для обратного индекса в `_generated/backlinks.md`. Любой dangling виден в секции `## Висячие ссылки`.

## 10. Расширение ALLOWED_AGENTS — процесс

Добавление нового short-name в allow-list требует:

1. **PR в `scripts/link_classifier.py`** — дополнить `ALLOWED_AGENTS`.
2. **Обновить `docs/link-conventions.md`** — секция 3, таблица реестра.
3. **Rationale в `CHANGELOG.md`** — зачем short-form, сколько существующих ссылок защищено.
4. **sync_check** — прогнать `python3 scripts/sync_check.py --workspace <vault>`, убедиться что dangling не вырос.

Без обновления этого документа PR блокируется (code review).
