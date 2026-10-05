# Workspace Makefile.
#
# Repositories, URLs and pins live in repos.yaml (read through scripts/repos.sh) and are
# mirrored in AGENTS.md and docs/mapping.md. `make status` fails if a ref/ repo drifts off
# its pin; `make bootstrap` recreates the whole workspace on a fresh machine.

REPOS         := scripts/repos.sh
WORKSPACE     := $(notdir $(CURDIR))


.DEFAULT_GOAL := help
.PHONY: help bootstrap pull status status-short pins diff log spec spec-check

help: ## Show this help
	@printf '\033[1m$(WORKSPACE)\033[0m\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\n  \033[2mrepos.yaml:'; for r in $$($(REPOS) list); do \
		case "$$($(REPOS) get $$r role)" in \
			reference) v=$$($(REPOS) get $$r tag); [ -n "$$v" ] || v=$$($(REPOS) get $$r commit) ;; \
			fork) v="$$($(REPOS) get $$r branch) off $$($(REPOS) get $$r base)" ;; \
			*) v="$$($(REPOS) get $$r branch)" ;; esac; \
		printf '\n    %-18s %s' "$$r" "$$v"; done; printf '\033[0m\n'

bootstrap: ## Clone every repo in repos.yaml at its pin and create .venv (SSH=1 for pushable fork clones)
	@scripts/bootstrap.sh $(if $(SSH),--ssh) $(if $(NOVENV),--no-venv) $(if $(DRY),--dry-run)

pull: ## Fast-forward every repo from its remote (never merges, rebases or discards; NOREF=1 skips ref/)
	@scripts/pull.sh $(if $(DRY),--dry-run) $(if $(NOREF),--no-ref) $(if $(SHORT),--short)

status: ## git status for the workspace and every repo in repos.yaml: fetches origin, reports ahead/behind, verifies pins and the generated spec (NOFETCH=1 to skip the fetch)
	@scripts/repo-status.sh && scripts/extract-spec.sh --check

status-short: ## Same as status, without the per-file listing
	@scripts/repo-status.sh --short && scripts/extract-spec.sh --check

spec: ## Regenerate docs/spec/yellowback-spec.md, the fork copy and both rpc-contract copies from the plan
	@scripts/extract-spec.sh

spec-check: ## Fail if any generated spec/contract copy is stale vs the plan (run by `make status`)
	@scripts/extract-spec.sh --check

pins: ## Print just the current HEAD of each repo (machine-readable)
	@printf '%-18s %-32s %s\n' repo ref commit
	@printf '%-18s %-32s %s\n' workspace "$$(git rev-parse --abbrev-ref HEAD)" "$$(git rev-parse --short HEAD)"
	@for r in $$($(REPOS) list); do \
		if [ "$$($(REPOS) get $$r role)" = reference ]; then ref=$$(git -C $$r describe --tags 2>/dev/null || echo 'commit (no tags)'); \
		else ref=$$(git -C $$r rev-parse --abbrev-ref HEAD); fi; \
		printf '%-18s %-32s %s\n' "$$r" "$$ref" "$$(git -C $$r rev-parse --short HEAD)"; \
	done

# Every fork (role `fork` in repos.yaml), each with its own branch and baseline: the v4.5.0 forks are on
# feature/yellowback-price-attest, the v6.20.0 forks (ycash6, librustzcash6) on feature/yellowback.
FORKS := $(shell for r in $$($(REPOS) list); do [ "$$($(REPOS) get $$r role)" = fork ] && printf '%s ' "$$r"; done)

diff: ## Fork deltas: every fork vs its -legacy baseline (the app repos have none)
	@for f in $(FORKS); do b="$$($(REPOS) get $$f base)"; br="$$($(REPOS) get $$f branch)"; \
	printf '\033[1m%s\033[0m\n' "$$f"; \
	out="$$(git -C $$f diff --stat "$$b...$$br")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno changes vs %s\033[0m\n' "$$b"; fi; done

log: ## Commits on each fork branch not in its baseline (the app repos have none)
	@for f in $(FORKS); do b="$$($(REPOS) get $$f base)"; br="$$($(REPOS) get $$f branch)"; \
	printf '\033[1m%s\033[0m\n' "$$f"; \
	out="$$(git -C $$f log --oneline --no-merges "$$b..$$br")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno commits on %s beyond %s\033[0m\n' "$$br" "$$b"; fi; done
