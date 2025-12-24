#!/usr/bin/env bash
# scripts/compliance_check.sh
# Purpose: fast, opinionated compliance checks for SOA1 consent + autonomy rules.
# Usage:
#   bash scripts/compliance_check.sh
#   bash scripts/compliance_check.sh --base HEAD~1
#   bash scripts/compliance_check.sh --path home-ai
#
# Exit codes:
#   0 = pass
#   1 = failed checks
#   2 = missing dependencies / repo state

set -euo pipefail

BASE_REF=""
ROOT_PATH="home-ai"
CONTEXT_LINES=20

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE_REF="${2:-}"; shift 2;;
    --path)
      ROOT_PATH="${2:-}"; shift 2;;
    --context)
      CONTEXT_LINES="${2:-20}"; shift 2;;
    -h|--help)
      cat <<EOF
Compliance check for SOA1 Home Assistant project.

Options:
  --base <git-ref>     Only scan changed files vs base ref (e.g., HEAD~1)
  --path <dir>         Root path to scan (default: home-ai)
  --context <N>        Context lines for gating checks (default: 20)

Examples:
  bash scripts/compliance_check.sh
  bash scripts/compliance_check.sh --base HEAD~1
  bash scripts/compliance_check.sh --path home-ai --context 30
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing dependency: $1" >&2
    exit 2
  }
}

need_cmd rg
need_cmd awk
need_cmd sed
need_cmd grep

if [[ -n "$BASE_REF" ]]; then
  need_cmd git
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "Not inside a git repo, but --base was provided." >&2
    exit 2
  }
fi

RED=$'\033[31m'
YELLOW=$'\033[33m'
GREEN=$'\033[32m'
RESET=$'\033[0m'

fail=0

print_section() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

# Build file list
# Build file list (exclude venv and other vendor dirs)
EXCLUDES=(
  "./venv"
  "./.venv"
  "./__pycache__"
  "./node_modules"
  "./agents/.*/venv"
)

is_excluded() {
  local f="$1"
  [[ "$f" == *"/venv/"* ]] && return 0
  [[ "$f" == *"/.venv/"* ]] && return 0
  [[ "$f" == *"/__pycache__/"* ]] && return 0
  [[ "$f" == *"/node_modules/"* ]] && return 0
  return 1
}

files_to_scan=()
if [[ -n "$BASE_REF" ]]; then
  mapfile -t files_to_scan < <(git diff --name-only "$BASE_REF" -- "$ROOT_PATH" \
    | grep -E '\.(py|md|txt|json|yml|yaml|sh)$' || true)
else
  mapfile -t files_to_scan < <(find "$ROOT_PATH" -type f \
    \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.json" -o -name "*.yml" -o -name "*.yaml" -o -name "*.sh" \) \
    2>/dev/null || true)
fi

# Filter excludes + exclude this script itself to avoid self-matches
filtered=()
for f in "${files_to_scan[@]}"; do
  if is_excluded "$f"; then
    continue
  fi
  if [[ "$f" == "./scripts/compliance_check.sh" || "$f" == "scripts/compliance_check.sh" ]]; then
    continue
  fi
  filtered+=("$f")
done
files_to_scan=("${filtered[@]}")

# Helper: run rg on only selected files
rg_files() {
  local pattern="$1"
  shift
  rg -n --no-heading --color never "$pattern" "${files_to_scan[@]}" 2>/dev/null || true
}

print_section "1) BANNED AUTONOMY PHRASES (language-level guardrails)"

# Keep this list tight and obvious. Add more as you observe drift.
banned_regex='(go ahead and|I'"'"'ll proceed|I will proceed|next, I will|I'"'"'ve started analyz|starting analys|analyzing now|I will now|I'"'"'m going to proceed|proceeding with)'

banned_hits="$(rg_files "$banned_regex")"
if [[ -n "$banned_hits" ]]; then
  echo "${RED}FAIL:${RESET} Found banned autonomy phrases:"
  echo "$banned_hits"
  fail=1
else
  echo "${GREEN}PASS:${RESET} No banned autonomy phrases found."
fi

print_section "2) SPECIALIST INVOCATION MUST BE CONSENT-GATED"

# Define "specialist call sites" patterns. Tune as your code evolves.
specialist_call_regex='(\bcall_phinance\s*\(|\binvoke_phinance\s*\(|\brun_phinance\s*\(|phinance\.call\s*\(|phinance_client\.call\s*\(|\bgenerate_(web|pdf)_report\s*\(|\bbuild_(web|pdf|infographic)_payload\s*\(|\bgenerate_infographic\s*\(|\binvoke_report\s*\(|\brun_report\s*\()'

# Define acceptable gating tokens in nearby context.
gate_regex='(require_consent|can_invoke_specialist|assert_consent|consent\.user_action_confirmed|user_action_confirmed)'

# Find all call sites with file:line
call_sites="$(rg_files "$specialist_call_regex")"

if [[ -z "$call_sites" ]]; then
  echo "${YELLOW}WARN:${RESET} No specialist call sites found in scanned files (this may be OK early on)."
else
  echo "Found specialist-related call sites:"
  echo "$call_sites"
  echo
  echo "Checking that each call site has a consent gate within the previous ${CONTEXT_LINES} lines..."

  # For each call site, inspect preceding context and require a gate token.
  # Format: path:line:content
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    file="$(echo "$hit" | sed -E 's/^([^:]+):([0-9]+):.*/\1/')"
    line="$(echo "$hit" | sed -E 's/^([^:]+):([0-9]+):.*/\2/')"

    start=$(( line - CONTEXT_LINES ))
    [[ $start -lt 1 ]] && start=1
    end=$(( line + 2 ))

    context="$(awk -v s="$start" -v e="$end" 'NR>=s && NR<=e {print}' "$file" 2>/dev/null || true)"

    if ! echo "$context" | rg -n --color never "$gate_regex" >/dev/null 2>&1; then
      echo "${RED}FAIL:${RESET} Ungated specialist call site:"
      echo "  $hit"
      echo "  --- context (${start}-${end}) ---"
      echo "$context" | sed 's/^/  /'
      echo "  -------------------------------"
      fail=1
    fi
  done <<< "$call_sites"

  if [[ $fail -eq 0 ]]; then
    echo "${GREEN}PASS:${RESET} All detected specialist call sites appear consent-gated (within context window)."
  fi
fi

print_section "3) ORCHESTRATOR MUST OWN CONSENT/INTENT (structural check)"

# Ensure orchestrator exists and includes consent constructs if it is among scanned files.
# (We do not fail if file isn't present yet; we warn.)
orch_candidates=(
  "$ROOT_PATH/soa1/orchestrator.py"
  "$ROOT_PATH/soa1/orchestrator.ts"
  "$ROOT_PATH/soa1/orchestrator.js"
)

orch_file=""
for c in "${orch_candidates[@]}"; do
  if [[ -f "$c" ]]; then
    orch_file="$c"
    break
  fi
done

if [[ -z "$orch_file" ]]; then
  echo "${YELLOW}WARN:${RESET} Could not find orchestrator at expected paths under $ROOT_PATH/soa1/ (ok early-stage)."
else
  echo "Orchestrator found: $orch_file"
  missing=0

  must_have=(
    'user_action_confirmed'
    'WAITING_INTENT|WAITING_INTENT\b'
    'CONSENT'
    'UserIntent|INTENT'
  )

  for pat in "${must_have[@]}"; do
    if ! rg -n --color never "$pat" "$orch_file" >/dev/null 2>&1; then
      echo "${RED}FAIL:${RESET} Orchestrator missing expected token/pattern: $pat"
      missing=1
      fail=1
    fi
  done

  if [[ $missing -eq 0 ]]; then
    echo "${GREEN}PASS:${RESET} Orchestrator includes expected consent/intent constructs."
  fi
fi

print_section "4) SPECIALISTS MUST NOT TALK TO USER (basic heuristic)"

# Heuristic: within home-ai/agents/*, flag any obvious user-facing message emission.
# Tune these markers to your codebase.
user_talk_regex='(emit_user_message|send_to_user|respond_to_user|chat_response|user-facing|ask the user|prompt the user|CONSENT_REQUEST|INTENT_OPTIONS)'

agent_hits="$(rg -n --no-heading --color never "$user_talk_regex" "$ROOT_PATH/agents" 2>/dev/null || true)"
if [[ -n "$agent_hits" ]]; then
  echo "${RED}FAIL:${RESET} Possible user-facing behavior detected inside agents/:"
  echo "$agent_hits"
  fail=1
else
  echo "${GREEN}PASS:${RESET} No obvious user-facing markers found inside agents/."
fi

print_section "RESULT"

if [[ $fail -eq 0 ]]; then
  echo "${GREEN}COMPLIANCE PASS${RESET}"
  exit 0
else
  echo "${RED}COMPLIANCE FAIL${RESET}"
  echo "Fix violations and re-run."
  exit 1
fi
