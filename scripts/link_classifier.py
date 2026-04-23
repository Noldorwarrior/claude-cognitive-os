"""
link_classifier — классификация wikilinks когнитивного воркспейса.

Разделяет целевые wikilinks на 6 классов:
  * ``vault``       — внутренние ссылки на ID или системные карточки 00–14.
  * ``plugin``      — внешние ссылки вида ``plugin:skill``.
  * ``agent``       — имена субагентов/команд из ALLOWED_AGENTS.
  * ``carry_over``  — файлы в ``projects/*/carry-over/*.md``.
  * ``memory``      — файлы в auto-memory-директории пользователя.
  * ``dangling``    — ничего из перечисленного; требует внимания.

Модуль используется обоими скриптами:
  * ``render_backlinks.py`` — группирует ссылки по классам в ``backlinks.md``;
  * ``sync_check.py``       — блокирует коммит при появлении ``dangling``.

Введено в v1.3.8 как часть задачи «D-полный» — системное решение 136 висячих
ссылок в vault. Подробности: ``projects/proj-014/carry-over/dangling-links-plan.md``.

Логика классификации намеренно pure-functional:
  * Никаких I/O внутри ``classify_target`` — вся индексация выполнена заранее.
  * Порядок проверок: plugin → agent → vault → carry_over → memory → dangling.
  * Бэктик-обёрнутые wikilinks (`` `[[pat-XXX]]` ``) снимаются до парсинга —
    это плейсхолдеры в шаблонах, а не ссылки.
"""

from __future__ import annotations

import os
import re
from glob import glob
from pathlib import Path

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Разрешённые «короткие» имена субагентов/системных скиллов без namespace.
# Расширять при появлении новых — см. docs/link-conventions.md.
ALLOWED_AGENTS: frozenset[str] = frozenset({
    "cog-verifier",
    "cog-archivist",
    "cog-detector",
    "init",
    "verification",
    "consolidate-memory",
})

# ID-префиксы vault. Ровно те же, что в render_backlinks.py / sync_check.py.
VAULT_ID_PREFIXES: tuple[str, ...] = (
    "pat", "wm", "ec", "km", "md", "term", "ent",
    "proj", "lesson", "sr", "audit", "domain", "cluster",
)

# Канонический паттерн для vault-ID: `<prefix>-NNN` (минимум 3 цифры).
VAULT_ID_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:" + "|".join(VAULT_ID_PREFIXES) + r")-\d{3,}$"
)

# Ссылка вида `plugin:skill`. Разрешены буквы/цифры/дефис/подчёркивание/точка
# в обоих сегментах — это покрывает все реальные плагины (`govdoc-analytics`,
# `claude-cognitive-os`, `events-presentations`, `productivity`, `verification`).
PLUGIN_LINK_PATTERN: re.Pattern[str] = re.compile(r"^[\w.\-]+:[\w.\-]+$")

# Системные карточки vault (имена без `.md`). 15 карточек 00–14.
CARD_NAMES: frozenset[str] = frozenset({
    "00_index", "01_user_profile", "02_patterns", "03_projects_registry",
    "04_meta_decisions", "05_global_glossary", "06_lessons_learned",
    "07_global_entities", "08_knowledge_maps", "09_working_mechanisms",
    "10_error_corrections", "11_confidence_scoring",
    "12_cross_project_graph", "13_self_reflection", "14_audit_log",
})

# DEPRECATED с v1.3.9. Оставлен для обратной совместимости внешних импортов.
# Новый код использует эшелонированный препроцессинг `strip_backticked` —
# он сам разбирается с fenced blocks, HTML-комментариями, escape-backticks
# и длинными inline-backticks (см. функцию ниже).
BACKTICKED_WIKILINK_RE: re.Pattern[str] = re.compile(r"`\[\[[^\]]+\]\]`")

# Эшелонированный препроцессинг (v1.3.10) — 5 стадий очистки текста от
# «не-ссылочных» контекстов до поиска wikilinks. Порядок стадий —
# strip_code → strip_comments (из ec-006 «Двойные бэктики вокруг
# HTML-коммента в cognitive_io»): сначала снимаются ВСЕ обёртки кода
# (fenced, двойные и одиночные backticks), которые могут СОДЕРЖАТЬ
# HTML-комменты, и только потом — живые HTML-комменты, оставшиеся вне
# кода. Обратный порядок (HTML раньше backticks) оставлял «осиротевшие»
# backticks вокруг исчезнувшего комментария, и non-greedy backtick-regex
# жадно склеивал их с далёкими парами — реальный инцидент ec-006 /
# lesson-004, воспроизведённый при первой реализации v1.3.9.
#
# Последовательность:
#
# 1. ESCAPE_BACKTICK_RE — escape-последовательности \`...\`.
#    Защищают «правильные примеры» в docs/link-conventions.md и
#    документации миграций; обрабатываются ПЕРВЫМИ, иначе INLINE_CODE_RE
#    интерпретирует `\`` как открывающий backtick.
# 2. FENCED_CODE_RE — fenced code blocks (```...``` с DOTALL).
#    Защищает примеры кода и YAML-конфигов в документации.
# 3. DOUBLE_INLINE_CODE_RE — двойные backticks ``...``.
#    Используются для документирования Markdown-синтаксиса внутри карт,
#    где содержимое может включать одиночные backticks (пример regex:
#    ``re.sub(r'`[^`]*`', '', body)``) или HTML-комменты
#    (``<!-- Шаблон -->``). Обрабатываются ПЕРЕД одиночными, иначе
#    INLINE_CODE_RE увидит их как пустые пары и пропустит содержимое.
# 4. INLINE_CODE_RE — обычные inline backticks `...`.
#    Покрывает и короткий (`[[X]]`), и длинный (`текст [[X]]`).
#    Сюда же попадают `<!-- -->` — однострочные HTML-комменты, обёрнутые
#    в одиночные backticks как пример.
# 5. HTML_COMMENT_RE — ЖИВЫЕ HTML-комментарии `<!-- ... -->`.
#    Сюда доходят только комменты, которые НЕ были обёрнуты в backticks —
#    то есть шаблоны записей в начале секций карт (исторически
#    lesson-003). DOTALL покрывает многострочные шаблоны.
FENCED_CODE_RE: re.Pattern[str] = re.compile(r"```.*?```", re.DOTALL)
HTML_COMMENT_RE: re.Pattern[str] = re.compile(r"<!--.*?-->", re.DOTALL)
ESCAPE_BACKTICK_RE: re.Pattern[str] = re.compile(r"\\`[^`\n]*\\`")
DOUBLE_INLINE_CODE_RE: re.Pattern[str] = re.compile(r"``[^\n]*?``")
INLINE_CODE_RE: re.Pattern[str] = re.compile(r"`[^`\n]*`")

# Обычный wikilink — используется скриптами для собственно извлечения ссылок.
# Здесь дублируется ради единого источника правды; клиенты импортируют его из
# этого модуля, а не объявляют локально.
WIKILINK_RE: re.Pattern[str] = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]")


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _preserve_newlines(match: re.Match[str]) -> str:
    """Заменяет многострочный матч на эквивалентное число ``\\n``.

    Парсеры-клиенты (`render_backlinks`, `sync_check`) индексируют
    найденные ссылки по номеру строки. Если просто вырезать fenced-блок
    через ``re.sub(..., "")``, все последующие строки «подтягиваются»
    вверх — номера перестают соответствовать оригинальному файлу и
    пользователь получает сообщение про строку, которой в карте нет.
    """
    return "\n" * match.group(0).count("\n")


def strip_backticked(text: str) -> str:
    """Эшелонированный препроцессинг — убирает «не-ссылочные» контексты.

    5 стадий в порядке strip_code → strip_comments (из ec-006):

      1. escape-последовательности \\`…\\` — убираются,
      2. fenced code blocks ```…``` — заменяются на ``\\n``×N,
      3. двойные inline backticks ``…`` — убираются,
      4. одиночные inline backticks `…` — убираются,
      5. ЖИВЫЕ HTML-комментарии <!-- … --> — заменяются на ``\\n``×N.

    Всё, что попадает внутрь этих контекстов, считается примером/кодом,
    а не настоящей wiki-ссылкой. Без такой очистки парсер видит
    «висячие» для каждого примера в документации самого синтаксиса
    wikilinks (`[[target]]` в link-conventions.md, шаблонные `[[pat-XXX]]`
    в lessons и т.п.).

    Порядок strip_code → strip_comments критичен: в картах встречается
    ``<!-- Шаблон -->`` и `<!-- -->` (HTML-комменты, обёрнутые в backticks
    как пример Markdown-синтаксиса). Если удалить HTML-коммент РАНЬШЕ
    backticks, окружающие backticks осиротеют и non-greedy DOUBLE_INLINE_
    CODE_RE склеит их с далёкими парами, съедая реальный текст. Сначала
    снимаем все обёртки кода, потом — оставшиеся живые комменты.

    Принцип соответствует pat-009 «Эшелонированный препроцессинг
    markdown-артефактов», lesson-003 «Фильтровать HTML-комментарии
    в парсерах карт до парсинга wiki-ссылок» и ec-006 «Двойные бэктики
    вокруг HTML-коммента в cognitive_io».

    Номера строк сохраняются: многострочные блоки (fenced, HTML-коммент)
    заменяются на эквивалентное число ``\\n``, чтобы клиенты могли
    корректно сообщать «файл:строка» для ссылок после блока.
    """
    text = ESCAPE_BACKTICK_RE.sub("", text)
    text = FENCED_CODE_RE.sub(_preserve_newlines, text)
    text = DOUBLE_INLINE_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    text = HTML_COMMENT_RE.sub(_preserve_newlines, text)
    return text


def parse_target(raw: str) -> tuple[str, str | None]:
    """Разбирает сырой текст wikilink-а: ``target#anchor|label`` → (target, anchor).

    Anchor опционален. Label (``|...``) не возвращается — он для отображения.
    """
    part = raw.split("|", 1)[0]
    if "#" in part:
        target, anchor = part.split("#", 1)
        return target.strip(), anchor.strip()
    return part.strip(), None


# ---------------------------------------------------------------------------
# Индексация внешних источников
# ---------------------------------------------------------------------------

def build_carry_over_index(workspace: Path) -> dict[str, str]:
    """Индексирует ``projects/*/carry-over/*.md`` → {stem: relative_path}.

    Ключ — имя файла без расширения (``block-2b``, ``handoff-to-block-2c``,
    ``dangling-links-inventory``). Значение — путь относительно воркспейса.
    """
    index: dict[str, str] = {}
    projects_dir = workspace / "projects"
    if not projects_dir.exists():
        return index
    for md in projects_dir.rglob("carry-over/*.md"):
        try:
            index[md.stem] = md.relative_to(workspace).as_posix()
        except ValueError:
            continue
    return index


def find_default_memory_dir() -> Path | None:
    """Пытается автоматически подобрать auto-memory-директорию.

    Не падает, если путь не найден: просто возвращает ``None``, и секция
    ``memory`` в отчёте будет пустой (а sync_check не увидит memory-файлов).

    Ищет по двум paths-источникам (в порядке приоритета):

      1. **Mac (хост пользователя)**:
         ``~/Library/Application Support/Claude/local-agent-mode-sessions
             /<session>/<env>/spaces/<space>/memory``
      2. **Sandbox (Linux)**: ``/sessions/*/mnt/.auto-memory``
         — монтируется Cowork-средой при запуске инструмента из sandbox.

    Такой dual-поиск нужен, чтобы один и тот же скрипт выдавал одинаковые
    результаты и на Mac, и из sandbox: иначе memory-ссылки
    (``[[feedback_git_hooks_from_sandbox]]``) классифицировались бы как
    ``dangling`` в одном контексте и ``memory`` в другом — штатный ложный
    сигнал при запуске render_backlinks/sync_check из sandbox.
    """
    patterns: list[str] = []

    # 1. Mac-путь (основной источник на хосте пользователя).
    home = Path.home()
    patterns.append(str(
        home / "Library" / "Application Support" / "Claude"
        / "local-agent-mode-sessions" / "*" / "*" / "spaces" / "*" / "memory"
    ))

    # 2. Sandbox-путь: Cowork монтирует auto-memory в /sessions/<id>/mnt/.auto-memory.
    patterns.append("/sessions/*/mnt/.auto-memory")

    matches: list[str] = []
    for pat in patterns:
        matches.extend(glob(pat))

    if not matches:
        return None

    # При нескольких совпадениях берём наиболее свежее — у нас обычно
    # активна ровно одна сессия, но страховка не лишняя.
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return Path(matches[0])


def build_memory_index(memory_dir: Path | None) -> dict[str, str]:
    """Индексирует ``memory_dir/*.md`` → {stem: filename}.

    ``memory_dir`` обычно:
      ``~/Library/Application Support/Claude/local-agent-mode-sessions/<session>/spaces/<space>/memory``

    Если путь не задан или не существует — возвращает пустой индекс
    (секция ``memory`` в backlinks.md будет пустой, это штатный режим).
    """
    if memory_dir is None:
        return {}
    if not memory_dir.exists() or not memory_dir.is_dir():
        return {}
    return {md.stem: md.name for md in memory_dir.glob("*.md")}


# ---------------------------------------------------------------------------
# Классификатор
# ---------------------------------------------------------------------------

def classify_target(
    target: str,
    vault_ids: set[str] | frozenset[str],
    carry_over_index: dict[str, str],
    memory_index: dict[str, str],
) -> str:
    """Определяет класс wikilink-target.

    Порядок проверок важен: ``plugin`` проверяется раньше ``vault``, потому
    что namespace-сегмент сам по себе может совпасть с именем карточки или
    ID. ``agent`` раньше ``carry_over``/``memory``, чтобы allow-list
    перекрывал случайные совпадения с именами файлов.

    Возвращает одну из строк:
      ``"vault"``, ``"plugin"``, ``"agent"``,
      ``"carry_over"``, ``"memory"``, ``"dangling"``.
    """
    # 1. Плагины — по двоеточию.
    if PLUGIN_LINK_PATTERN.match(target):
        return "plugin"

    # 2. Системные агенты — по allow-list.
    if target in ALLOWED_AGENTS:
        return "agent"

    # 3. Vault: ID (`pat-001`) или системная карточка (`02_patterns`).
    if VAULT_ID_PATTERN.match(target) or target in CARD_NAMES:
        return "vault" if target in vault_ids else "dangling"

    # 4. Carry-over (`block-2b`, `handoff-to-block-2c`).
    if target in carry_over_index:
        return "carry_over"

    # 5. Memory-файлы (`feedback_git_hooks_from_sandbox`).
    if target in memory_index:
        return "memory"

    # 6. Всё остальное — висячая.
    return "dangling"


__all__ = [
    "ALLOWED_AGENTS",
    "VAULT_ID_PREFIXES",
    "VAULT_ID_PATTERN",
    "PLUGIN_LINK_PATTERN",
    "CARD_NAMES",
    "BACKTICKED_WIKILINK_RE",
    "FENCED_CODE_RE",
    "HTML_COMMENT_RE",
    "ESCAPE_BACKTICK_RE",
    "DOUBLE_INLINE_CODE_RE",
    "INLINE_CODE_RE",
    "WIKILINK_RE",
    "strip_backticked",
    "parse_target",
    "build_carry_over_index",
    "build_memory_index",
    "find_default_memory_dir",
    "classify_target",
]
