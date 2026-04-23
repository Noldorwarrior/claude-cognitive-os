# Starter Workspace — claude-cognitive-os v1.3

Это минимальный пример когнитивного воркспейса. Скопируйте папку
или используйте как референс при создании своего.

## Состав

- **15 карточек** `0N_*.md` и `1N_*.md` — «ядро» воркспейса.
- **`.obsidian/`** — предзаполненная конфигурация Obsidian.
- **README.md** — этот файл.

## Быстрый старт

```bash
# Скопируйте в желаемое место
cp -r examples/starter_workspace ~/my-cognitive-workspace

# Откройте в Obsidian как vault:
# File → Open vault → выбрать ~/my-cognitive-workspace

# Экспортируйте путь для скриптов и хуков
echo 'export CLAUDE_WORKSPACE="$HOME/my-cognitive-workspace"' >> ~/.zshrc
exec zsh
```

## Что внутри уже заполнено

- `00_index.md` — корневой индекс со счётчиками (все нули).
- `01_user_profile.md` — шаблон профиля (заполните вручную).
- `02_patterns.md` — один образец `pat-001` как пример формата.
- `03_projects_registry.md` — один образец `proj-001`.
- Остальные карты — структура с нуля, добавляйте по мере работы.

## После копирования

1. Заполните `01_user_profile.md` своими данными.
2. Удалите образцы `pat-001` и `proj-001` (если они вам не нужны).
3. Запустите `[[init]]` для регистрации или начните работу вручную.

## Obsidian-интеграция

Папка `.obsidian/` содержит:
- `workspace.json` — раскладка панелей (левая — файлы, правая — граф).
- `hotkeys.json` — хоткеи для быстрой навигации.
- `core-plugins.json` — включён Graph View и Backlinks.

## Связанное

- [[../docs/quick_start]] — полный quick start.
- [[../docs/architecture]] — архитектура.
- [[../docs/thresholds_reference]] — пороги.
