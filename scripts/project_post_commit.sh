#!/usr/bin/env bash
# project_post_commit.sh — post-commit hook для логирования коммитов в
# cognitive OS vault.
#
# Поведение:
#   1. Определяет project_id: frontmatter `project_id:` в CLAUDE.md репо;
#      fallback — `proj-auto-<basename>`.
#   2. Определяет vault: $CLAUDE_WORKSPACE или ~/Documents/Claude/cognitive_os/.
#      Если vault или его 00_index.md отсутствует — exit 0 (не ломаем commit).
#   3. Создаёт cognitive_os/projects/<id>/ и log.md при отсутствии.
#   4. Дописывает строку `YYYY-MM-DD HH:MM <sha7> <subject>` в log.md.
#   5. Пишет строку external-event в 14_audit_log.md (если существует).
#   6. При автосоздании проекта пишет вторую строку audit «auto-registered».
#
# Marker для installer:
# COGNITIVE-OS-HOOK-MARKER=project_post_commit
#
# Exit code: всегда 0 (post-commit не должен ломать git workflow).

set -euo pipefail

# --- сбор контекста репо --------------------------------------------------

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    exit 0  # вызов вне git-репо — тихо выходим
fi
REPO_NAME="$(basename "$REPO_ROOT")"

# --- project_id -----------------------------------------------------------

get_project_id() {
    local claude_md="$REPO_ROOT/CLAUDE.md"
    if [[ -f "$claude_md" ]]; then
        # Ищем project_id внутри первого YAML-frontmatter блока (между --- и ---).
        local pid
        pid="$(awk '
            BEGIN { in_fm = 0; seen = 0 }
            /^---[[:space:]]*$/ {
                if (!seen) { in_fm = 1; seen = 1; next }
                else       { exit }
            }
            in_fm && /^project_id:[[:space:]]*/ {
                sub(/^project_id:[[:space:]]*/, "")
                sub(/[[:space:]]+$/, "")
                gsub(/["'\'']/, "")
                print
                exit
            }
        ' "$claude_md")"
        if [[ -n "$pid" ]]; then
            printf '%s\n' "$pid"
            return
        fi
    fi
    printf 'proj-auto-%s\n' "$REPO_NAME"
}

PROJECT_ID="$(get_project_id)"

# --- vault ----------------------------------------------------------------

VAULT="${CLAUDE_WORKSPACE:-$HOME/Documents/Claude/cognitive_os}"

if [[ ! -d "$VAULT" ]] || [[ ! -f "$VAULT/00_index.md" ]]; then
    printf 'post-commit (cognitive-os): vault not found at %s — skip\n' "$VAULT" >&2
    exit 0
fi

# --- commit метаданные ----------------------------------------------------

SHA="$(git rev-parse --short=7 HEAD)"
SUBJECT="$(git log -1 --pretty=%s)"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"

# --- project folder + log.md ----------------------------------------------

PROJ_DIR="$VAULT/projects/$PROJECT_ID"
LOG_FILE="$PROJ_DIR/log.md"
NEW_PROJECT=0

if [[ ! -d "$PROJ_DIR" ]]; then
    mkdir -p "$PROJ_DIR"
    NEW_PROJECT=1
fi

if [[ ! -f "$LOG_FILE" ]]; then
    cat > "$LOG_FILE" <<EOF
---
project_id: $PROJECT_ID
repo_path: $REPO_ROOT
created: $TIMESTAMP
source: project_post_commit.sh
---

# Commit log — $PROJECT_ID

EOF
fi

printf '%s %s %s\n' "$TIMESTAMP" "$SHA" "$SUBJECT" >> "$LOG_FILE"

# --- 14_audit_log.md ------------------------------------------------------

AUDIT="$VAULT/14_audit_log.md"
if [[ -f "$AUDIT" ]]; then
    {
        if [[ "$NEW_PROJECT" -eq 1 ]]; then
            printf -- '- external-event %s: auto-registered project %s from %s\n' \
                "$TIMESTAMP" "$PROJECT_ID" "$REPO_ROOT"
        fi
        printf -- '- external-event %s: commit %s in %s (%s) — %s\n' \
            "$TIMESTAMP" "$SHA" "$PROJECT_ID" "$REPO_NAME" "$SUBJECT"
    } >> "$AUDIT"
fi

exit 0
