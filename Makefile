# ydollar-workspace
#
# Pins live here and are mirrored in AGENTS.md and docs/mapping.md.
# `make status` fails if a ref/ repo drifts off its pin.

DIGIBYTE_PIN := v9.26.5
YCASH_PIN    := v4.5.0
DD_BRANCH    := digidollar
DD_BASE      := ycash-legacy

export DIGIBYTE_PIN YCASH_PIN DD_BRANCH DD_BASE

.DEFAULT_GOAL := help
.PHONY: help status status-short pins diff log

help: ## Show this help
	@printf '\033[1mydollar-workspace\033[0m\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\n  \033[2mpins: digibyte=%s  ycash=%s  fork=%s off %s\033[0m\n' \
		'$(DIGIBYTE_PIN)' '$(YCASH_PIN)' '$(DD_BRANCH)' '$(DD_BASE)'

status: ## git status across all four repos, with pin verification
	@scripts/repo-status.sh

status-short: ## Same as status, without the per-file listing
	@scripts/repo-status.sh --short

pins: ## Print just the current HEAD of each repo (machine-readable)
	@printf '%-14s %-12s %s\n' repo ref commit
	@printf '%-14s %-12s %s\n' workspace \
		"$$(git rev-parse --abbrev-ref HEAD)" "$$(git rev-parse --short HEAD)"
	@printf '%-14s %-12s %s\n' ref/digibyte \
		"$$(git -C ref/digibyte describe --tags 2>/dev/null)" \
		"$$(git -C ref/digibyte rev-parse --short HEAD)"
	@printf '%-14s %-12s %s\n' ref/ycash \
		"$$(git -C ref/ycash describe --tags 2>/dev/null)" \
		"$$(git -C ref/ycash rev-parse --short HEAD)"
	@printf '%-14s %-12s %s\n' ycash-dd \
		"$$(git -C ycash-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C ycash-dd rev-parse --short HEAD)"

diff: ## Full fork delta: ycash-legacy...digidollar
	@out="$$(git -C ycash-dd diff --stat '$(DD_BASE)...$(DD_BRANCH)')"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '\033[2mno changes vs %s\033[0m\n' '$(DD_BASE)'; fi

log: ## Commits on the fork branch not in the baseline
	@out="$$(git -C ycash-dd log --oneline --no-merges '$(DD_BASE)..$(DD_BRANCH)')"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '\033[2mno commits on %s beyond %s\033[0m\n' '$(DD_BRANCH)' '$(DD_BASE)'; fi
