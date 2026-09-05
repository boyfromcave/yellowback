# ydollar-workspace
#
# Pins live here and are mirrored in AGENTS.md and docs/mapping.md.
# `make status` fails if a ref/ repo drifts off its pin.

DIGIBYTE_PIN  := v9.26.5
YCASH_PIN     := v4.5.0
YECWALLET_PIN := v4.5.0
DD_BRANCH     := feature/digidollar
DD_BASE       := ycash-legacy
WALLET_BASE   := yecwallet-legacy

export DIGIBYTE_PIN YCASH_PIN YECWALLET_PIN DD_BRANCH DD_BASE WALLET_BASE

.DEFAULT_GOAL := help
.PHONY: help status status-short pins diff log

help: ## Show this help
	@printf '\033[1mydollar-workspace\033[0m\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\n  \033[2mpins: digibyte=%s  ycash=%s  yecwallet=%s  forks: %s off %s / %s\033[0m\n' \
		'$(DIGIBYTE_PIN)' '$(YCASH_PIN)' '$(YECWALLET_PIN)' '$(DD_BRANCH)' '$(DD_BASE)' '$(WALLET_BASE)'

status: ## git status across all six repos, with pin verification
	@scripts/repo-status.sh

status-short: ## Same as status, without the per-file listing
	@scripts/repo-status.sh --short

pins: ## Print just the current HEAD of each repo (machine-readable)
	@printf '%-14s %-20s %s\n' repo ref commit
	@printf '%-14s %-20s %s\n' workspace \
		"$$(git rev-parse --abbrev-ref HEAD)" "$$(git rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/digibyte \
		"$$(git -C ref/digibyte describe --tags 2>/dev/null)" \
		"$$(git -C ref/digibyte rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/ycash \
		"$$(git -C ref/ycash describe --tags 2>/dev/null)" \
		"$$(git -C ref/ycash rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/yecwallet \
		"$$(git -C ref/yecwallet describe --tags 2>/dev/null)" \
		"$$(git -C ref/yecwallet rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ycash-dd \
		"$$(git -C ycash-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C ycash-dd rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' yecwallet-dd \
		"$$(git -C yecwallet-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C yecwallet-dd rev-parse --short HEAD)"

diff: ## Fork deltas: ycash-dd and yecwallet-dd vs their -legacy baselines
	@for r in "ycash-dd $(DD_BASE)" "yecwallet-dd $(WALLET_BASE)"; do set -- $$r; \
	printf '\033[1m%s\033[0m\n' "$$1"; \
	out="$$(git -C $$1 diff --stat "$$2...$(DD_BRANCH)")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno changes vs %s\033[0m\n' "$$2"; fi; done

log: ## Commits on each fork branch not in its baseline
	@for r in "ycash-dd $(DD_BASE)" "yecwallet-dd $(WALLET_BASE)"; do set -- $$r; \
	printf '\033[1m%s\033[0m\n' "$$1"; \
	out="$$(git -C $$1 log --oneline --no-merges "$$2..$(DD_BRANCH)")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno commits on %s beyond %s\033[0m\n' '$(DD_BRANCH)' "$$2"; fi; done
