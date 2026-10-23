#!/usr/bin/env bash
# Test input for contrib/semgrep/rules/workspace.yaml (semgrep --test). Never run.
ok_ref() {
  local dir="$1"
  run git -c x=y clone --quiet "$url" "$dir"
  case "$(git -C "$dir" rev-parse HEAD)" in "$2"*) ;; *) exit 1 ;; esac
}
bootstrap_app() {
  run git clone --quiet --branch "$branch" "$url" "$dir"
}
# ruleid: yellowback.scripts.pinned-clone-unverified
bad_clone() {
  git clone --quiet "$url" "$dir"
  echo done
}
# ruleid: yellowback.scripts.pipe-to-shell
curl -fsSL https://example.com/install.sh | sh
# ruleid: yellowback.scripts.pipe-to-shell
wget -qO- https://example.com/x | sudo bash
# ok: yellowback.scripts.pipe-to-shell
curl -fsSLo f https://example.com/x && sha256sum -c f.sha256
# ruleid: yellowback.scripts.clone-without-manifest
git clone https://github.com/a/b.git b
