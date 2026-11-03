# feat: one git worktree + one Claude session per ZenTao requirement.
# Sourced from ~/.bashrc (a shell function, so `feat go` can cd). Local-only, not committed.
#
#   feat new <zentao-id> [change-name] [base-branch]   create worktree, then start Claude with /zentao <id>
#   feat go  <zentao-id>                               cd into it and continue the last Claude session
#   feat ls                                            list requirements in progress
#   feat rm  <zentao-id>                               remove a finished worktree (checks it is clean and pushed)

_FEAT_MAIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_FEAT_ROOT="${WT_ROOT:-$HOME/wt}"
_FEAT_COUNTRIES=" {{AP_COUNTRY_CODES}} "

feat() {
  case "${1:-ls}" in
    new) shift; _feat_new "$@" ;;
    go)  _feat_go "${2:-}" ;;
    ls)  _feat_ls ;;
    rm)  _feat_rm "${2:-}" ;;
    *)   sed -n '4,7p' "$_FEAT_MAIN/docs/agents/feat.sh" | sed 's/^#   //' ;;
  esac
}

# path of the worktree whose branch is <owner>/feature-<id>-*, empty when none
_feat_path() {
  git -C "$_FEAT_MAIN" worktree list --porcelain | awk -v id="$1" -v owner="${FEAT_BRANCH_OWNER:-{{BRANCH_OWNER}}}" '
    /^worktree /{p=substr($0,10)} /^branch /{if ($2 ~ "^refs/heads/" owner "/feature-" id "-") print p}' | head -1
}

_feat_title() {
  (cd "$_FEAT_MAIN" && python3 .claude/skills/zentao/scripts/zentao.py show "$1" 2>/dev/null) \
    | sed -n 's/^# [^ ]* #[0-9]* //p' | head -1 | sed 's/&amp;/\&/g'
}

# base branch from the title tag: 【{{AP_PROJECT}}-{{AP_CC_UPPER}}】/【{{AP_PROJECT}}{{AP_CC_PASCAL}}】 -> {{AP_CC_BRANCH}}, {{AP_SUBLINE}} -> {{AP_SUBLINE_BRANCH}}, no tag -> {{AP_MAIN_BRANCH}}
_feat_base() {
  local title="$1" cc
  if echo "$title" | grep -qi '{{AP_SUBLINE}}'; then echo {{AP_SUBLINE_BRANCH}}; return; fi
  cc="$(echo "$title" | grep -o '【[^】]*】' | head -1 | sed -E 's/^【{{AP_PROJECT}}[- ]?//I; s/】$//' | tr 'A-Z' 'a-z')"
  case "$_FEAT_COUNTRIES" in *" $cc "*) [ -n "$cc" ] && { echo "master_$cc"; return; } ;; esac
  echo {{AP_MAIN_BRANCH}}
}

_feat_new() {
  local id="${1:-}" name="${2:-}" base="${3:-}" title path branch answer
  [ -z "$id" ] && { echo "usage: feat new <zentao-id> [change-name] [base-branch]"; return 1; }
  path="$(_feat_path "$id")"
  if [ -n "$path" ]; then echo "#$id already has a worktree: $path"; _feat_go "$id"; return; fi

  title="$(_feat_title "$id")"
  [ -n "$title" ] && echo "#$id $title" || echo "warning: cannot read ZenTao #$id, continue with manual input"
  while [ -z "$name" ]; do
    read -r -p "change name (english, kebab-case, e.g. {{AP_CC}}-loan-cap): " name
    case "$name" in *[!a-z0-9-]*) echo "only a-z 0-9 -"; name="" ;; esac
  done
  if [ -z "$base" ]; then
    base="$(_feat_base "$title")"
    read -r -p "base branch [$base] (Enter to accept, or type another): " answer
    base="${answer:-$base}"
  fi

  branch="${FEAT_BRANCH_OWNER:-{{BRANCH_OWNER}}}/feature-${id}-${name}"
  path="$_FEAT_ROOT/${id}-${name}"
  git -C "$_FEAT_MAIN" show-ref --verify --quiet "refs/heads/$branch" && { echo "branch exists: $branch"; return 1; }
  git -C "$_FEAT_MAIN" fetch -q origin "$base" || return 1
  mkdir -p "$_FEAT_ROOT"
  git -C "$_FEAT_MAIN" worktree add -q -b "$branch" "$path" "origin/$base" || return 1
  git -C "$path" branch -q --unset-upstream 2>/dev/null
  _feat_link "$path"
  mkdir -p "$path/.harness" "$path/.mvn" "$path/.m2-local"
  printf '# Progress\n\n- %s 起：禅道 #%s %s；分支 %s，基线 origin/%s。\n' "$(date +%F)" "$id" "$title" "$branch" "$base" > "$path/.harness/progress.md"
  # SNAPSHOT installs stay in this worktree; third-party jars are read from the shared repository
  printf -- '-Dmaven.repo.local=%s\n-Dmaven.repo.local.tail=%s\n' "$path/.m2-local" "$HOME/.m2/repository" > "$path/.mvn/maven.config"
  _feat_ignore "$path"

  echo "ready: $path  ($branch from origin/$base)"
  cd "$path" && claude "/zentao $id"
}

# symlink the main worktree's git-ignored harness files (rules, dev.sh, skills, settings) so they stay single-source
_feat_link() {
  local path="$1" entry
  while IFS= read -r entry; do
    entry="${entry%/}"
    case "$entry" in .harness|.mvn|.m2-local|*target|*.iml|*.idea|*.project|*.classpath|*.settings|*.log) continue ;; esac
    [ -e "$path/$entry" ] && continue
    mkdir -p "$(dirname "$path/$entry")"
    ln -s "$_FEAT_MAIN/$entry" "$path/$entry"
  done < <(git -C "$_FEAT_MAIN" status --ignored --porcelain=v1 | sed -n 's/^!! //p')
}

# a pattern with a trailing slash does not match a symlink, so add slash-less patterns where needed
_feat_ignore() {
  local path="$1" exclude entry
  exclude="$(cd "$_FEAT_MAIN" && cd "$(git rev-parse --git-common-dir)" && pwd)/info/exclude"
  git -C "$path" status --porcelain | sed -n 's/^?? //p' | while IFS= read -r entry; do
    echo "/${entry%/}" >> "$exclude"
  done
  [ -z "$(git -C "$path" status --porcelain)" ] || { echo "warning: worktree not clean:"; git -C "$path" status --short; }
}

_feat_go() {
  local path
  [ -z "$1" ] && { echo "usage: feat go <zentao-id>"; return 1; }
  path="$(_feat_path "$1")"
  [ -z "$path" ] && { echo "no worktree for #$1, see: feat ls"; return 1; }
  cd "$path" && { claude --continue || claude; }
}

_feat_ls() {
  local path branch dirty ahead note
  printf '%-8s %-6s %-12s %s\n' ID DIRTY PUSH "BRANCH / PATH"
  git -C "$_FEAT_MAIN" worktree list --porcelain | awk '/^worktree /{p=substr($0,10)} /^branch /{print p "\t" substr($2,12)}' |
  while IFS=$'\t' read -r path branch; do
    dirty="$(git -C "$path" status --porcelain | wc -l)"
    if git -C "$path" rev-parse -q --verify "origin/$branch" >/dev/null; then
      ahead="$(git -C "$path" rev-list --count "origin/$branch..HEAD")"; note="+$ahead"
      [ "$ahead" = 0 ] && note="ok"
    else
      note="none"
    fi
    printf '%-8s %-6s %-12s %s\n' "$(echo "$branch" | sed -n 's#^[^/]*/feature-\([^-]*\)-.*#\1#p')" "$dirty" "$note" "$branch  $path"
  done
  echo "DIRTY = uncommitted files; PUSH: ok = pushed, +N = commits not pushed, none = branch never pushed"
}

_feat_rm() {
  local path branch answer
  [ -z "$1" ] && { echo "usage: feat rm <zentao-id>"; return 1; }
  path="$(_feat_path "$1")"
  [ -z "$path" ] && { echo "no worktree for #$1"; return 1; }
  [ "$path" = "$_FEAT_MAIN" ] && { echo "refuse: $path is the main worktree"; return 1; }
  branch="$(git -C "$path" branch --show-current)"
  [ -n "$(git -C "$path" status --porcelain)" ] && { echo "refuse: uncommitted changes in $path"; git -C "$path" status --short; return 1; }
  git -C "$path" fetch -q origin "$branch" 2>/dev/null
  if ! git -C "$path" rev-parse -q --verify "origin/$branch" >/dev/null || [ "$(git -C "$path" rev-list --count "origin/$branch..HEAD")" != 0 ]; then
    echo "refuse: $branch has commits not pushed to origin"; return 1
  fi
  read -r -p "remove $path and local branch $branch? [y/N] " answer
  [ "$answer" = y ] || return 1
  case "$PWD" in "$path"*) cd "$_FEAT_MAIN" ;; esac
  git -C "$_FEAT_MAIN" worktree remove "$path" && git -C "$_FEAT_MAIN" branch -q -D "$branch" && echo "removed #$1 ($branch is still on origin)"
}
