# CHANGELOG

Все значимые изменения фиксируются в этом файле.

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: [SemVer](https://semver.org/lang/ru/).

## [1.3.8] — 2026-04-23

### Added

- **`scripts/link_classifier.py`** — классификатор wikilinks на 6 классов (`vault`, `plugin`, `agent`, `carry_over`, `memory`, `dangling`). Используется `render_backlinks.py` и `audit_contradictions.py` для отличения «висячих ссылок» от намеренных ссылок на артефакты за пределами vault (плагин, agent-memory, carry-over между сессиями). Снимает ложноположительные `dangling_link` на ссылки типа `[[claude-cognitive-os:patterns]]` или `[[agent-memory:feedback_xxx]]`, которые раньше шумели в audit-отчётах.
- **Pre-flight проверка в скилле `reflect`** — перед запуском self-reflection цикла проверяется: (1) наличие `11_confidence_scoring.md`, (2) корректность YAML frontmatter, (3) отсутствие открытых `audit-NNN` типа `sync_drift`. При провале — понятное сообщение пользователю вместо тихого падения в середине рефлексии. Рационал: рефлексия пишет в несколько карточек одновременно; падение после первой записи оставляло vault в частично-обновлённом состоянии.
- **`scripts/install_hooks.sh` + `scripts/project_post_commit.sh`** — git post-commit хук для проектов в `~/Documents/Claude/Projects/*`: после коммита триггерит запись в `03_projects_registry.md` через chain-wrapper (не перезаписывает существующие post-commit). Устанавливается вручную командой `bash scripts/install_hooks.sh <project_path>` из Terminal пользователя (не из sandbox — подробности в feedback-memory «Git-хуки ставим из Terminal пользователя, не из sandbox»).
- **`docs/link-conventions.md`** — единый источник истины по 6 классам wikilinks, ALLOWED_AGENTS allow-list (6 имён: cog-verifier, cog-archivist, cog-detector, init, verification, consolidate-memory) и обязательному namespace-префиксу для всех skills плагина (`[[claude-cognitive-os:migrate]]`, не `[[migrate]]`). Добавлен процесс расширения allow-list: PR в link_classifier.py + реестр в этом документе + rationale в CHANGELOG. До 1.3.8 правила жили только в комментариях кода, и новые авторы carry-over-планов регулярно создавали false-positive dangling — этот документ снимает класс ошибок на уровне конвенции.
- **`skills/graph/SKILL.md`: секция «Исполнитель»** — явное указание главного скрипта `scripts/render_graph.py`, его вызовов из hook-контекста (`--if-changed`, таймаут 5 сек) и явного контекста (флаги `--project`, `--domain`, `--conflict-only`, `--mermaid-only`, `--offline`), а также вспомогательных `paginate_projects.py` и `render_mermaid.py`. До фикса SKILL.md был единственным скиллом, где не было упоминания своего главного исполнителя — 9 из 10 остальных скиллов следовали паттерну «скилл описывает что → скрипт делает как», graph выбивался. Pre-release doc-drift найден в Этапе 2 Фазы 0 аудита v1.3.8.

### Fixed

- **`docs/migration_guide.md`: удалено обещание несуществующего `scripts/migrate_workspace.py`**. В v1.0.1–1.3.7 «Вариант B: неинтерактивный» рекомендовал команду `python3 scripts/migrate_workspace.py --from /old/path --to /new/path [--dry-run]`, но сам скрипт никогда не существовал (аналогичный wishful-thinking паттерн как у удалённого `cognitive-os-workspaces.json`). Новый пользователь, выполняющий миграцию v1.0.1 → v1.3.x по неинтерактивному сценарию, получал `python3: can't open file 'scripts/migrate_workspace.py'` на самой первой команде. В 1.3.8 секция переписана: статус явно помечен как «запланирован к релизу 1.3.9», единственный рабочий путь — **Вариант А (интерактивный диалог через скилл `[[claude-cognitive-os:migrate]]`)** + ручной рецепт шагов, уже описанный в гайде.
- **`docs/migration_guide.md` шаг 5: `templates/<card>.template.md` → `templates/<card>.md`**. Гайд описывал несуществующую конвенцию имени шаблонов с суффиксом `.template.md` — реально в репозитории используется простой паттерн `templates/<card>.md` (15 файлов: `00_index.md` … `14_audit_log.md`). Новый пользователь, следующий гайду, не находил шаблоны по описанному пути. Найдено М13 (декомпозиция) Этапа 3 П13 Аудитора.
- **2 false-positive dangling ссылки в `projects/proj-014/carry-over/task-07-closure-gate-plan.md`**: `[[migrate]]` и `[[reflect]]` → `[[claude-cognitive-os:migrate]]` и `[[claude-cognitive-os:reflect]]`. Skill-имена плагина требуют полного namespace (см. `docs/link-conventions.md` § 4); без него `link_classifier` корректно маркирует их как dangling. На 2026-04-22 sync_report показывал ровно эти 2 ошибки — после правок `sync_report.md` = `error 0`, `backlinks.md` = `dangling 0/0`.
- **`MANUAL_ALL_PROJECTS.md` frontmatter: `version: 1.0 (для плагина v1.3.7)` → `version: 1.1 (для плагина v1.3.8)`** + добавлено поле `updated: 2026-04-23`. Мануал содержательно валиден для 1.3.8 (релиз doc-only), но явная привязка к 1.3.7 вводила в заблуждение. Найдено М18 (триангуляция) Этапа 3 П13 Аудитора.
- **`templates/00_index.md`: `total_cards: 11` → `total_cards: 15`**. Legacy-значение унаследовано от cognitive-os skill v1.0.1 (там было 11 активных карт); в плагине v1.3 — 15 карточек 00-14. До фикса каждый свежий vault, созданный через `init`, стартовал с рассогласованным счётчиком (sync_check репортил mismatch с первой минуты). После фикса `declared=actual=15` сразу после init.

### Changed

- **Унификация имени vault-папки: `cognitive-os/` → `cognitive_os/`** во всех docs, skills и templates. Имя плагина (`claude-cognitive-os`) и имена скиллов (`cognitive-os-core`, `cognitive-os-graph`, `cognitive-os-calibration`) — остаются с дефисом, это namespace плагина и не путь vault. Граница явная: дефис = пакет/скилл, подчёркивание = vault-папка. Метаморфический инвариант: 0 вхождений `cognitive-os/` как путь vault, 29 вхождений `cognitive_os/`, 0 CamelCase. Обратная совместимость: пользователи с существующим vault'ом по пути `cognitive-os/` продолжают работать — скрипты читают путь из `$CLAUDE_WORKSPACE` / `--workspace`, а не зашивают имя.

### Removed

- **Удалены упоминания `~/.claude/cognitive-os-workspaces.json`** из docs и скиллов (6 мест: `docs/architecture.md` § Bootstrap/Init workflow, `docs/migration_guide.md` FAQ «Хуки не срабатывают», `examples/starter_workspace/README.md` § Быстрый старт, `skills/init/SKILL.md` § шаг 5 «Регистрация воркспейса», `skills/init/SKILL.md` таблица команд строка «покажи существующие воркспейсы», `skills/status/SKILL.md` § 1 «Обнаружение воркспейса»). Git archaeology показала: все 6 упоминаний появились в одном стартовом коммите v1.3.3 (20.04.2026) как wishful-thinking в документации; реализации никогда не было (0 упоминаний в `scripts/`, `hooks/`, `agents/`), ни один релиз 1.3.4-1.3.7 не трогал эту тему. Single-vault через `$CLAUDE_WORKSPACE` покрывает все реальные сценарии пользователя; реестр проектов внутри vault обеспечивается `03_projects_registry.md`. Удаление — не breaking, т.к. fantom-реестра никогда не существовало на диске.

### Chore

- **Удалены артефакты из dev/**: `.DS_Store` (macOS Finder metadata) и `test_rm.tmp` (остаток от ручной проверки). Оба — нулевой функциональный вес, попали в git через недосмотр.

### Rationale

Релиз 1.3.8 закрывает три независимых хвоста одновременно, потому что по отдельности каждый меньше порога отдельного patch-релиза, но суммарно они устраняют три разных класса шума: (1) ложноположительные `dangling_link` в audit (новый `link_classifier.py`), (2) рассогласование счётчиков сразу после init (`total_cards` фикс), (3) зомби-документация про never-implemented feature (workspaces.json removal). Pre-flight в reflect и git post-commit хуки — подготовка инфраструктуры: оба не меняют поведение существующих vault'ов, но добавляют точки безопасности перед следующими релизами. Обратная совместимость 100%: все изменения либо строго additive (link_classifier, Pre-flight, git hooks), либо правят документацию/шаблоны, не затрагивая API скриптов.

## [1.3.7] — 2026-04-21

### Changed

- **`RESERVED_RANGE_RE` сам поглощает хвостовой inline-комментарий**. Regex в `scripts/sync_check.py` расширен до `...(\d{3})\s*(?:#.*)?$` — одна точка правды вместо двух. До правки `parse_reserved_ranges` дополнительно обрезал ` #...` / `\t#...` строковой операцией перед `RESERVED_RANGE_RE.match()` — в v1.3.6 это было необходимо, потому что regex был строгий (`^...$`) и не допускал хвоста. Теперь срез удалён; грамматика reserved-range явно включает хвостовой whitespace + `#comment`, что соответствует YAML 1.2 § 6.6 (комментарий начинается с `#` после whitespace). Побочный эффект: допустимыми стали формы вроде `ent-019..ent-029#нет пробела перед #` (раньше бы не распознались из-за требования ` #`/`\t#` в строковом срезе).

### Documented

- **Контракт inline-комментариев зафиксирован в docstring `parse_frontmatter`**. Явно указано: комментарии ведут себя по YAML 1.2 § 6.6 (`#` после whitespace либо в начале строки); полностью закомментированные строки удаляются парсером, inline-комментарии внутри значений оставляются consumer'у. Это переводит «допущение по формату комментариев» (верификация v1.3.6, логические механизмы — 90% уверенности) в зафиксированную часть контракта.

### Rationale

Оба изменения — хвост одного решения: «закрыть оставшееся допущение про формат комментариев из П5-верификации релиза v1.3.6». Вариант A (локальный regex-фикс) и вариант B (документирование контракта) сделаны вместе, потому что по отдельности они неполные: regex без документирования — скрытая семантика; документирование без regex — риск, что следующий consumer снова будет делать свой строковый срез. Теперь грамматика видна в коде и в docstring одновременно. Обратная совместимость 100%: всё, что парсилось в v1.3.6, продолжает парситься в v1.3.7 идентично.

## [1.3.6] — 2026-04-21

### Fixed

- **YAML-lists во frontmatter больше не ломают `parse_frontmatter`**. Примитивный парсер в `scripts/sync_check.py` расширен: ключ с пустым значением + следующие строки вида `  - item` теперь распознаются как `list[str]`. До фикса 16 warnings `frontmatter_parse` («Строка без `:` — `- govsector`») шумели на `11_confidence_scoring.md` (12 warnings по 12 доменам) и `05_global_glossary.md` (4 warnings по 4 кластерам терминов). После фикса sync даёт 0 warnings этого класса. Поведение для простых `key: value` и «плоских» mapping-подобных блоков (`thresholds:` + `  pattern: 3`) не изменилось — вложенные ключи продолжают попадать на верхний уровень с уже снятым отступом, что согласовано с существующими call-site'ами (`thresholds`, `counters`).

### Added

- **Frontmatter-ключ `reserved_ranges` и поддержка в `find_gaps`**. Формат:

      reserved_ranges:
        - ent-019..ent-029    # зарезервировано под организации (org-блок)
        - pat-050..pat-055

  Новая функция `parse_reserved_ranges(workspace)` сканирует frontmatter всех карточек и собирает множество зарезервированных ID-номеров по каждому префиксу; `find_gaps(..., reserved=...)` пропускает щели, полностью покрытые этим множеством. Inline YAML-комментарии (` # ...` / `\t# ...`) в строках-элементах списка срезаются перед regex-match через `RESERVED_RANGE_RE`. Правый конец диапазона может быть записан полностью (`ent-019..ent-029`) или сокращённо (`ent-019..029`) — во втором случае левый префикс наследуется. Для `07_global_entities.md` объявлен резерв `ent-019..ent-029` (зарезервировано под будущий блок организаций); до фикса sync репортил `id_gap ent-: 018 → 030 (gap 12)` как info — теперь подавляется на корректном семантическом основании.

### Rationale

Два патча идут одним релизом, потому что оба расширяют контракт frontmatter карточек. YAML-lists — базовое YAML-поведение, которого изначально не хватало в самописном парсере; его отсутствие выталкивало реально валидные frontmatter'ы в класс warnings. `reserved_ranges` закрывает сценарий «ID-диапазон зарезервирован, но записи ещё не созданы» без грубого повышения `max_id_gap` — это типичная ситуация при пред-аллокации под организационный блок или под будущую группу паттернов. Оба изменения не ломают обратную совместимость: карточки без `reserved_ranges` ведут себя как раньше; frontmatter'ы без YAML-lists парсятся так же, как парсились.

## [1.3.5] — 2026-04-21

### Fixed

- **Шаблонные записи больше не засчитываются как реальные (рассинхрон №2)**. В `scripts/sync_check.py` и `scripts/render_graph.py` добавлена константа `HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->", re.MULTILINE)` и функция `strip_html_comments(text)`. В `sync_check.count_ids()` текст карточек пропускается через `strip_html_comments` перед построчным поиском заголовков `^###?\s+<prefix>\d{3}`. В `render_graph.build_graph()` — то же самое перед обоими `extract_ids(content)` (сбор узлов и сбор wikilink-рёбер). До фикса заголовки, обёрнутые в `<!-- Шаблон записи: ### pat-001 — ... -->`, попадали в счётчики `actual` (wm=10 vs 9, ent=15 vs 12) и в граф как фантомные узлы. После фикса `actual` равен реально активным записям, а граф не содержит узлов из примеров-заготовок.
- **Fallback на `active_<prefix>s` во frontmatter (рассинхрон №1)**. `scripts/sync_check.parse_declared_counters()` теперь, если в `00_index.md` нет секции `## Counters`, собирает декларации из frontmatter всех карточек через маппинг `active_patterns → patterns`, `active_mechanisms → mechanisms`, `active_errors → errors`, `active_knowledge_maps → knowledge_maps`, `active_meta_decisions → meta_decisions`, `active_terms → terms`, `active_glossary_terms → terms` (алиас в 00_index), `active_entities → entities`, `active_projects → projects`, `active_lessons → lessons`, `active_reflections → reflections`, `active_audits → audits`, `active_domains → domains`, `confidence_domains → domains` (алиас), `active_clusters → clusters`, `cross_project_clusters → clusters` (алиас). До фикса воркспейсы с порогами/счётчиками во frontmatter карточек (текущий дефолт инициализации) получали 13 info `counter_missing` на каждом прогоне sync — теперь декларации находятся, и сравнение `declared vs actual` работает по существу.
- **Canonical `CARD_PREFIX_MAP` и новый формат таблицы `## Counters` в отчёте**. Маппинг «ID-префикс → имя счётчика» вынесен из локальной переменной `build_report` на уровень модуля (`sync_check.CARD_PREFIX_MAP`) и переиспользован в `render_report`. Таблица Counters теперь одна строка на префикс: `| Prefix | Counter | Actual | Declared | Status |`. До фикса отчёт показывал каждый префикс дважды — один раз как `pat-` с пустым Declared, второй как `patterns` с нулевым Actual, — что было визуально обманчиво (создавало впечатление рассинхрона там, где его нет).

### Housekeeping

- **Пример в `02_patterns.md` переименован `pat-007` → `pat-009`**, чтобы номер не совпадал с активным `pat-007 — ПРОМТ-workflow`. Пример живёт внутри `<!-- Пример: ... -->` и после `strip_html_comments` в счётчики не попадает; правка сделана для человеческой читаемости, а не для сборки.

### Rationale

Два патча идут одним релизом, потому что оба затрагивают `sync_check.py` и адресуют одну и ту же проблему — отчёт sync раньше показывал info/warnings, не связанные с реальным состоянием воркспейса, и это сбивало сигнал. Комбинация «HTML-комментарий вокруг шаблонов + strip_html_comments в парсерах» сохраняет шаблоны в исходниках карточек (они полезны при ручном добавлении записей), но убирает их из автоматических подсчётов. Fallback на frontmatter сохраняет обратную совместимость: воркспейсы, объявляющие счётчики в `## Counters` секции 00_index, продолжают работать без изменений.

## [1.3.4] — 2026-04-21

### Added

- **Два новых ID-префикса в `render_graph.py`**: `insight-NNN` (amber `#F39C12` — озарение) и `insurance-NNN` (dark teal `#16A085` — защита). Граф теперь покрывает все 15 префиксов воркспейса (было 13). Согласованно правлены три места: `ID_PATTERNS` dict, `NODE_COLORS` dict и HTML groups JS-literal в `render_html()`. Это финализация Track A, который висел в working copy после релиза v1.3.3.

### Fixed

- **Детерминизм `render_graph.py`**: итерация по `set[str]` в `build_graph()` заменена на `sorted(...)` в трёх местах — обход `extract_ids(content)` при сборке узлов, обход `source_ids` при сборке wikilink-рёбер и обход `projects_dir.rglob("*.md")`. До фикса порядок узлов и рёбер в `_generated/graph.html` и `_generated/graph.mermaid` зависел от `PYTHONHASHSEED` (рандомизируется между процессами Python по умолчанию). Счётчики и содержимое всегда были корректны (161 узел / 6129 рёбер стабильно), но SHA256 файлов менялся от запуска к запуску — это ломало любые downstream-проверки на «изменился ли граф». После фикса SHA256 идентичен между 6 прогонами (3 с дефолтным random seed + 3 с явными `PYTHONHASHSEED=42/137/2026`).

### Rationale

Track A нужно было довыпустить, чтобы граф не молчаливо игнорировал `insight-NNN` и `insurance-NNN`-узлы. Детерминизм рендера снимает класс ложноположительных «изменений» в графе, что особенно важно для будущих hooks/CI-сверок и для корректной работы скилла [[backlinks]] через `render_graph.py`.

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
