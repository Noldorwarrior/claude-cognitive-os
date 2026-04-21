---
project_id: proj-014
---

# claude-cognitive-os — плагин когнитивного воркспейса

Плагин для Claude Code. Vault-based cognitive workspace с картами 00-14.

## Ключевые файлы
- `.claude-plugin/plugin.json` — манифест плагина (источник истины для версии)
- `scripts/project_post_commit.sh` — git hook для логирования коммитов в vault
- `scripts/install_hooks.sh` — инсталлятор хука
- `skills/` — скиллы плагина
- `agents/` — субагенты (cog-archivist, cog-verifier, cog-detector)

## Vault
`$CLAUDE_WORKSPACE` → `~/Documents/Claude/cognitive_os/` — целевой vault. Коммиты этого репо логируются в `cognitive_os/projects/proj-014/log.md`.

## Self-hook
В этом же репо стоит post-commit hook, который ссылается на `scripts/project_post_commit.sh` в этом же репо. Разработка плагина логируется в vault как любой другой проект.
