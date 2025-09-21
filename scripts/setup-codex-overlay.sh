#!/usr/bin/env bash
set -euo pipefail

# =========================
# UI helpers
# =========================
color() { printf "\033[%sm%s\033[0m" "${1:-0}" "${2:-}"; }
info()  { echo "$(color '1;36' '›')" "$@"; }
warn()  { echo "$(color '1;33' '⚠')" "$@"; }
ok()    { echo "$(color '1;32' '✓')" "$@"; }
err()   { echo "$(color '1;31' '✗')" "$@"; }

ask_yn() { # ask_yn "Question" default(no|yes)
  local q="${1:-Proceed?}" d="${2:-no}" ans
  case "$d" in
    y|Y|yes) read -rp "$q [Y/n] " ans || true; [[ -z "${ans:-}" || "$ans" =~ ^[Yy]$ ]];;
    *)       read -rp "$q [y/N] " ans || true; [[ "$ans" =~ ^[Yy]$ ]];;
  esac
}

need_cmd() { command -v "$1" >/dev/null 2>&1 || { err "Required command '$1' not found in PATH."; return 1; }; }

# =========================
# Environment / detection
# =========================
need_cmd ln
need_cmd awk
need_cmd sed
need_cmd date

if ! command -v git >/dev/null 2>&1; then
  warn "git not found — .gitignore guard can still work later via shell hooks."
fi

if ! command -v codex >/dev/null 2>&1; then
  warn "The 'codex' CLI was not found."
  ask_yn "Continue anyway (you can install codex later)?" no || exit 1
else
  ok "codex found: $(command -v codex)"
fi

DEFAULT_SHELL="${SHELL:-}"
[[ -z "$DEFAULT_SHELL" ]] && DEFAULT_SHELL="$(ps -p ${PPID:-$$} -o comm= 2>/dev/null || true)"
DEFAULT_SHELL_BASENAME="${DEFAULT_SHELL##*/}"

choose_shells() {
  local choices=() pick
  command -v zsh >/dev/null 2>&1 && choices+=("zsh")
  command -v bash >/dev/null 2>&1 && choices+=("bash")
  if ((${#choices[@]}==0)); then
    err "Neither zsh nor bash available. Aborting."
    exit 1
  fi
  info "Detected shells: ${choices[*]}"
  if [[ " ${choices[*]} " == *" zsh "* ]]; then
    pick="zsh"
  else
    pick="${choices[0]}"
  fi
  echo "$pick"
}

PRIMARY_SHELL="$(choose_shells)"
info "Primary target shell: $PRIMARY_SHELL"

RC_ZSH="${ZDOTDIR:-$HOME}/.zshrc"
RC_BASH="$HOME/.bashrc"
[[ -f "$HOME/.bashrc" || ! -f "$HOME/.bash_profile" ]] || RC_BASH="$HOME/.bash_profile"

ZSH_SNIPPET="$HOME/.codex_overlay.zsh"
BASH_SNIPPET="$HOME/.codex_overlay.bash"
GLOBAL_HOME="$HOME/.codex"

# =========================
# Write snippets
# =========================
write_zsh() {
cat >"$ZSH_SNIPPET" <<"ZSH_SNIP"
# --- Codex per-project overlay (zsh) -----------------------------------------
# Keeps auth/logs/sessions in ~/.codex and overlays them into PROJECT/.codex
# while letting .codex/prompts (and optionally .codex/commands) stay local.

export CODX_GLOBAL_HOME="$HOME/.codex"

_codx_find_project_root() {
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    [[ -d "$dir/.codex" || -d "$dir/.codex/prompts" || -d "$dir/.codex/commands" ]] && { print -r -- "$dir"; return 0; }
    dir="${dir:h}"
  done
  return 1
}

_codx_overlay_global_into_project() {
  local proj_codex="$1"
  [[ -n "$proj_codex" ]] || return 1
  mkdir -p "$proj_codex"
  mkdir -p "$proj_codex/prompts"
  # mkdir -p "$proj_codex/commands"  # uncomment if you want a local commands dir

  setopt local_options null_glob extended_glob
  local src base dest
  for src in "$CODX_GLOBAL_HOME"/^(prompts|commands)(N); do
    base="${src:t}"
    dest="$proj_codex/$base"
    if [[ -e "$dest" && ! -L "$dest" ]]; then
      continue
    fi
    ln -sfn -- "$src" "$dest"
  done
}

typeset -ga _CODX_GI_HEADER=(
  "# Codex overlay: keep auth/logs in ~/.codex; only track per-project prompts/commands"
  "# Ignore .codex/* but re-include .codex/prompts and .codex/commands below"
)

typeset -ga _CODX_GI_RULES=(
  ".codex/*"
  "!.codex/prompts/"
  "!.codex/prompts/**"
  "!.codex/commands/"
  "!.codex/commands/**"
)

_codx_in_git_repo() {
  command -v git >/dev/null 2>&1 || return 1
  git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

_codx_gitignore_ensure_trailing_blankline() {
  local gi="$1"
  [[ -f "$gi" ]] || return 0
  if [[ -n "$(tail -c1 "$gi" 2>/dev/null)" ]]; then echo >> "$gi"; fi
  if [[ -n "$(tail -n1 "$gi" | tr -d ' \t\r')" ]]; then echo >> "$gi"; fi
}

_codx_gitignore_append_missing() {
  local gi="$1" ; shift
  [[ -f "$gi" ]] || : > "$gi"
  _codx_gitignore_ensure_trailing_blankline "$gi"
  local line missing=()
  for line in "$@"; do
    grep -Fqx -- "$line" "$gi" || missing+=("$line")
  done
  [[ ${#missing[@]} -eq 0 ]] && return 0
  if ! grep -Fqx -- "${_CODX_GI_HEADER[1]}" "$gi"; then
    printf "%s\n" "${_CODX_GI_HEADER[@]}" >> "$gi"
    echo >> "$gi"
    print -u2 -- "✅ Inserted Codex header at end of $gi"
  fi
  for line in "${missing[@]}"; do
    print -r -- "$line" >> "$gi"
  done
}

_codx_ensure_gitignore() {
  local proj_root="$1" gi="$proj_root/.gitignore"
  _codx_in_git_repo "$proj_root" || return 0
  local has_broad=""
  if [[ -f "$gi" ]] && grep -Eq '^[[:space:]]*\.codex/?[[:space:]]*$' "$gi"; then
    has_broad=1
  fi
  local missing=() r
  for r in "${_CODX_GI_RULES[@]}"; do
    if [[ ! -f "$gi" ]] || ! grep -Fqx -- "$r" "$gi"; then
      missing+=("$r")
    fi
  done
  [[ -z "$has_broad" && ${#missing[@]} -eq 0 ]] && return 0

  print -u2 -- "⚠️  Codex: .gitignore at $gi needs attention."
  [[ -n "$has_broad" ]] && print -u2 -- "   - Found a broad \".codex\" rule that prevents re-including prompts/commands."
  (( ${#missing[@]} )) && print -u2 -- "   - Missing recommended rules: ${missing[*]}"

  local reply
  if [[ ! -f "$gi" ]]; then
    read -q "reply?Create .gitignore with Codex header and rules now? [y/N] "; echo
    if [[ "$reply" == [yY] ]]; then
      : > "$gi"
      _codx_gitignore_append_missing "$gi" "${_CODX_GI_RULES[@]}"
      print -u2 -- "✅ Created $gi with Codex header and rules."
    fi
    return 0
  fi

  read -q "reply?Patch .gitignore (add Codex header, remove broad rule, append safe rules)? [y/N] "; echo
  if [[ "$reply" == [yY] ]]; then
    local ts backup tmp
    ts=$(date +%Y%m%d-%H%M%S)
    backup="$gi.bak_codex_$ts"
    cp -p -- "$gi" "$backup" 2>/dev/null || cp -p "$gi" "$backup"
    if [[ -n "$has_broad" ]]; then
      tmp="$gi.tmp_codex_$ts"
      awk '!/^[[:space:]]*\.codex\/?[[:space:]]*$/' "$gi" > "$tmp" && mv "$tmp" "$gi"
    fi
    _codx_gitignore_append_missing "$gi" "${_CODX_GI_RULES[@]}"
    print -u2 -- "✅ Updated $gi (backup: $backup)"
  else
    print -u2 -- "ℹ️  Skipped updating $gi. Broad \".codex\" rules will hide prompts/commands from Git."
  fi
}

_codx_switch_codex_home() {
  local proj_root proj_codex
  if proj_root="$(_codx_find_project_root)"; then
    proj_codex="$proj_root/.codex"
    export CODEX_HOME="$proj_codex"
    _codx_overlay_global_into_project "$proj_codex"
    _codx_ensure_gitignore "$proj_root"
  else
    export CODEX_HOME="$CODX_GLOBAL_HOME"
  fi
}

autoload -Uz add-zsh-hook
add-zsh-hook chpwd _codx_switch_codex_home
_codx_switch_codex_home
# --- end Codex overlay (zsh) ------------------------------------------------
ZSH_SNIP
}

write_bash() {
cat >"$BASH_SNIPPET" <<"BASH_SNIP"
# --- Codex per-project overlay (bash) ----------------------------------------
# Uses PROMPT_COMMAND to update CODEX_HOME on directory changes.

export CODX_GLOBAL_HOME="$HOME/.codex"

_codx_find_project_root() {
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.codex" || -d "$dir/.codex/prompts" || -d "$dir/.codex/commands" ]]; then
      printf '%s\n' "$dir"; return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

_codx_overlay_global_into_project() {
  local proj_codex="$1"
  [[ -n "$proj_codex" ]] || return 1
  mkdir -p "$proj_codex"
  mkdir -p "$proj_codex/prompts"
  # mkdir -p "$proj_codex/commands"  # uncomment if you want a local commands dir

  shopt -s nullglob extglob
  local src base dest
  for src in "$CODX_GLOBAL_HOME"/!(prompts|commands); do
    base="$(basename "$src")"
    dest="$proj_codex/$base"
    if [[ -e "$dest" && ! -L "$dest" ]]; then
      continue
    fi
    ln -sfn -- "$src" "$dest"
  done
  shopt -u nullglob extglob
}

_CODX_GI_HEADER_1="# Codex overlay: keep auth/logs in ~/.codex; only track per-project prompts/commands"
_CODX_GI_HEADER_2="# Ignore .codex/* but re-include .codex/prompts and .codex/commands below"

declare -a _CODX_GI_RULES=(
  ".codex/*"
  "!.codex/prompts/"
  "!.codex/prompts/**"
  "!.codex/commands/"
  "!.codex/commands/**"
)

_codx_in_git_repo() {
  command -v git >/dev/null 2>&1 || return 1
  git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

_codx_gitignore_ensure_trailing_blankline() {
  local gi="$1"
  [[ -f "$gi" ]] || return 0
  if [[ -n "$(tail -c1 "$gi" 2>/dev/null || true)" ]]; then echo >> "$gi"; fi
  if [[ -n "$(tail -n1 "$gi" | tr -d ' \t\r')" ]]; then echo >> "$gi"; fi
}

_codx_gitignore_append_missing() {
  local gi="$1"; shift
  [[ -f "$gi" ]] || : > "$gi"
  _codx_gitignore_ensure_trailing_blankline "$gi"

  local line missing=()
  for line in "$@"; do
    if ! grep -Fqx -- "$line" "$gi" 2>/dev/null; then
      missing+=("$line")
    fi
  done
  [[ ${#missing[@]} -eq 0 ]] && return 0

  if ! grep -Fqx -- "$_CODX_GI_HEADER_1" "$gi" 2>/dev/null; then
    printf "%s\n" "$_CODX_GI_HEADER_1" "$_CODX_GI_HEADER_2" >> "$gi"
    echo >> "$gi"
    >&2 echo "✅ Inserted Codex header at end of $gi"
  fi

  for line in "${missing[@]}"; do
    printf "%s\n" "$line" >> "$gi"
  done
}

_codx_ensure_gitignore() {
  local proj_root="$1" gi="$proj_root/.gitignore"
  _codx_in_git_repo "$proj_root" || return 0

  local has_broad=""
  if [[ -f "$gi" ]] && grep -Eq '^[[:space:]]*\.codex/?[[:space:]]*$' "$gi"; then
    has_broad=1
  fi

  local missing=() r
  for r in "${_CODX_GI_RULES[@]}"; do
    if [[ ! -f "$gi" ]] || ! grep -Fqx -- "$r" "$gi"; then
      missing+=("$r")
    fi
  done

  [[ -z "$has_broad" && ${#missing[@]} -eq 0 ]] && return 0

  >&2 echo "⚠️  Codex: .gitignore at $gi needs attention."
  [[ -n "$has_broad" ]] && >&2 echo "   - Found a broad \".codex\" rule that prevents re-including prompts/commands."
  (( ${#missing[@]} )) && >&2 echo "   - Missing recommended rules: ${missing[*]}"

  local reply
  if [[ ! -f "$gi" ]]; then
    read -r -p "Create .gitignore with Codex header and rules now? [y/N] " reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
      : > "$gi"
      _codx_gitignore_append_missing "$gi" "${_CODX_GI_RULES[@]}"
      >&2 echo "✅ Created $gi with Codex header and rules."
    fi
    return 0
  fi

  read -r -p "Patch .gitignore (add Codex header, remove broad rule, append safe rules)? [y/N] " reply
  if [[ "$reply" =~ ^[Yy]$ ]]; then
    local ts backup tmp
    ts="$(date +%Y%m%d-%H%M%S)"
    backup="$gi.bak_codex_$ts"
    cp -p -- "$gi" "$backup" 2>/dev/null || cp -p "$gi" "$backup"
    if [[ -n "$has_broad" ]]; then
      tmp="$gi.tmp_codex_$ts"
      awk '!/^[[:space:]]*\.codex\/?[[:space:]]*$/' "$gi" > "$tmp" && mv "$tmp" "$gi"
    fi
    _codx_gitignore_append_missing "$gi" "${_CODX_GI_RULES[@]}"
    >&2 echo "✅ Updated $gi (backup: $backup)"
  else
    >&2 echo "ℹ️  Skipped updating $gi. Broad \".codex\" rules will hide prompts/commands from Git."
  fi
}

_codx_switch_codex_home() {
  local proj_root proj_codex
  if proj_root="$(_codx_find_project_root)"; then
    proj_codex="$proj_root/.codex"
    export CODEX_HOME="$proj_codex"
    _codx_overlay_global_into_project "$proj_codex"
    _codx_ensure_gitignore "$proj_root"
  else
    export CODEX_HOME="$CODX_GLOBAL_HOME"
  fi
}

# Install PROMPT_COMMAND hook once
case "${PROMPT_COMMAND:-}" in
  *_codx_switch_codex_home*) :;;
  "") PROMPT_COMMAND="_codx_switch_codex_home";;
  *)  PROMPT_COMMAND="_codx_switch_codex_home; $PROMPT_COMMAND";;
esac

# Run once for current shell
_codx_switch_codex_home
# --- end Codex overlay (bash) -----------------------------------------------
BASH_SNIP
}

mkdir -p "$GLOBAL_HOME"

# Write/overwrite snippets only with consent
if [[ -f "$ZSH_SNIPPET" ]]; then
  info "zsh snippet exists at $ZSH_SNIPPET"
  if ask_yn "Overwrite zsh snippet with latest version?" no; then
    write_zsh; ok "Updated $ZSH_SNIPPET"
  fi
else
  write_zsh; ok "Wrote $ZSH_SNIPPET"
fi

if [[ -f "$BASH_SNIPPET" ]]; then
  info "bash snippet exists at $BASH_SNIPPET"
  if ask_yn "Overwrite bash snippet with latest version?" no; then
    write_bash; ok "Updated $BASH_SNIPPET"
  fi
else
  write_bash; ok "Wrote $BASH_SNIPPET"
fi

# =========================
# Wire into RC files (ask!)
# =========================
wire_rc() {
  local rc="$1" snippet="$2" shellname="$3"
  [[ -n "$rc" && -n "$snippet" ]] || return 0
  [[ -f "$snippet" ]] || return 0
  [[ -f "$rc" ]] || touch "$rc"

  # If RC already references our snippet, skip or offer to re-add
  if grep -Fq "$snippet" "$rc"; then
    info "$shellname RC already sources $snippet"
    return 0
  fi

  # Heuristic: if RC already contains our function name (inline setup),
  # warn and offer to skip adding another hook.
  if grep -Fq "_codx_switch_codex_home" "$rc"; then
    warn "$shellname RC already seems to contain a Codex overlay (inline)."
    ask_yn "Add snippet sourcing anyway?" no || return 0
  else
    ask_yn "Append snippet sourcing to $rc for $shellname?" yes || return 0
  fi

  local backup="${rc}.bak_codex_$(date +%Y%m%d-%H%M%S)"
  cp -p "$rc" "$backup" 2>/dev/null || true
  {
    echo
    echo "# Load Codex per-project overlay (installed by setup-codex-overlay.sh)"
    if [[ "$shellname" == "zsh" ]]; then
      echo "if [[ -f \"$snippet\" ]]; then source \"$snippet\"; fi"
    else
      echo "[ -f \"$snippet\" ] && source \"$snippet\""
    fi
  } >> "$rc"
  ok "Added source line to $rc (backup: $backup)"
}

# Ask which shells to wire
TARGET_ZSH=false
TARGET_BASH=false

if [[ "$PRIMARY_SHELL" == "zsh" ]]; then
  TARGET_ZSH=true
  ask_yn "Also install for bash RC?" no && TARGET_BASH=true
else
  TARGET_BASH=true
  ask_yn "Also install for zsh RC?" yes && TARGET_ZSH=true
fi

$TARGET_ZSH  && wire_rc "$RC_ZSH" "$ZSH_SNIPPET" "zsh"
$TARGET_BASH && wire_rc "$RC_BASH" "$BASH_SNIPPET" "bash"

# =========================
# Optional one-shot run now
# =========================
echo
if ask_yn "Run a one-shot overlay + .gitignore check for THIS directory now?" yes; then
  if [[ "$PRIMARY_SHELL" == "zsh" && $(command -v zsh) ]]; then
    # Run in a separate zsh to avoid sourcing zsh code into bash
    zsh -c "source '$ZSH_SNIPPET'; _codx_switch_codex_home" || true
  elif [[ "$PRIMARY_SHELL" == "bash" && $(command -v bash) ]]; then
    bash -c "source '$BASH_SNIPPET'; _codx_switch_codex_home" || true
  else
    warn "Primary shell not available for one-shot. Skipping."
  fi
fi

echo
ok "Codex per-project overlay setup finished."
info "To activate hooks in new terminals:"
echo "  - zsh : run 'source \"$RC_ZSH\"' or open a new shell"
echo "  - bash: run 'source \"$RC_BASH\"' or open a new shell"