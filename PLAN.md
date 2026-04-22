# copier-template-validator — Project Plan

## What It Is

A GitHub Action (published to the Marketplace) that validates any AF-ecosystem Copier template by:
1. Reading its `copier-module.yaml` to discover dependencies
2. Rendering each dependency in topological order to produce real answer files
3. Rendering the target template with `--defaults`
4. The calling workflow then runs whatever steps it needs against the rendered output

---

## Decisions Made

### Repo
- Separate public repo under `datarobot-oss` from day 1 — required by GitHub Marketplace
- Name: `copier-template-validator`
- `action.yml` at root (Marketplace requirement)

### Action Interface

```yaml
# The action only renders — calling workflow owns post-render steps
- uses: datarobot-oss/copier-template-validator@v1
  with:
    working-directory: ./af-component-agent
    rendered-dir: ./rendered/agent_generic_base
    copier-args: '--defaults --data agent_template_framework=base'

# Calling workflow defines named steps after render
- name: Install
  run: uvx --from go-task-bin task install
- name: Test
  run: uvx --from go-task-bin task test-coverage
```

### Dependency Graph (frozen)

```
af-base            →  (none)
af-llm             →  af-base
af-mcp             →  af-base
af-fastapi         →  af-base
af-component-agent →  af-base + af-llm + af-mcp
af-react           →  af-base + af-fastapi

Max depth: 2 levels. af-base is always root.
```

### Resolution Strategy
- Read `copier-module.yaml` from the target repo
- Topologically sort deps (max 2 levels, no deep recursion needed)
- Clone each dep, render it with `--defaults`, extract its `.datarobot/answers/*.yml`
- Place answer files where the target template expects them before rendering
- Action runs inside `ghcr.io/astral-sh/uv:python3.11-bookworm` container (same as all AF component CIs)

---

## Phased Delivery

| Phase | Work | Status |
|-------|------|--------|
| **1** | `action.yml` + `resolve_deps.py` + `self-test.yml` | ✅ Done |
| **2** | Self-test goes green end-to-end | ✅ Done |
| **3** | Roll out to all 5 components | 🔲 Not started |
| **4** | Tag `v1` release + Marketplace + Copier forum post | 🔲 Not started |

---

## Repo Structure

```
copier-template-validator/
├── action.yml                  ← GitHub Action entry point (composite)
├── scripts/
│   └── resolve_deps.py         ← reads copier-module.yaml, renders deps, produces answer files
├── tests/
│   └── test_resolve_deps.py    ← unit tests for resolver (not yet written)
├── .github/
│   └── workflows/
│       └── self-test.yml       ← validates the action against af-component-agent itself
├── PLAN.md
└── README.md                   ← not yet written
```

---

## Open Items

- [ ] af-component-agent `fix/copier-module-mcp-url` PR merged
- [ ] Self-test goes green
- [ ] Inspect af-fastapi and af-react fixture shapes before Phase 3
- [ ] Write `tests/test_resolve_deps.py`
- [ ] Write `README.md`
