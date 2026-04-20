# copier-template-validator — Project Plan

## What It Is

A GitHub Action (published to the Marketplace) that validates any AF-ecosystem Copier template by:
1. Reading its `copier-module.yaml` to discover dependencies
2. Rendering each dependency in topological order to produce real answer files
3. Rendering the target template with `--defaults`
4. Running a user-specified list of commands against the rendered output

---

## Decisions Made

### Repo
- Separate public repo under `datarobot-oss` from day 1 — required by GitHub Marketplace
- Name: `copier-template-validator`
- `action.yml` at root (Marketplace requirement)

### Action Interface

```yaml
- uses: datarobot-oss/copier-template-validator@v1
  with:
    copier-args: '--defaults --data agent_template_framework=base'
    actions: |
      uv lock --check
      uvx --from go-task-bin task install
      uvx --from go-task-bin task lint-check
      uvx --from go-task-bin task test-coverage
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
- Replaces the current hardcoded fixture files in af-component-agent

### What We're Stealing From af-component-agent
- `.github/actions/render-copier-instance/action.yml` — the render logic
- `fixtures/.datarobot/answers/*.yml` — the answer file format/shape
- `fixtures/` structure — post-render file copies (Taskfile, infra scaffolding)
- `afcomponentagent-framework-test.yaml` — the matrix CI pattern

---

## Phased Delivery

| Phase | Work | Exit Criterion |
|-------|------|----------------|
| **1** | Repo skeleton + port existing render logic (static fixtures) | af-component-agent CI passes using the new action |
| **2** | `resolve_deps.py` — dynamic dep resolution | Delete static fixtures, CI still green |
| **3** | Roll out to all 5 components | All 5 component CIs green |
| **4** | Tag `v1` release + Marketplace + Copier forum post | Action discoverable on Marketplace |

---

## Repo Structure (target)

```
copier-template-validator/
├── action.yml                  ← GitHub Action entry point (composite)
├── scripts/
│   ├── resolve_deps.py         ← reads copier-module.yaml, renders deps, produces answer files
│   └── render_and_run.sh       ← renders main template + runs user-provided actions
├── tests/
│   └── test_resolve_deps.py    ← unit tests for resolver logic
├── .github/
│   └── workflows/
│       └── self-test.yml       ← validates the action against af-component-agent itself
├── PLAN.md
└── README.md
```

---

## Open Items

- [ ] Repo URL confirmed: https://github.com/datarobot-oss/copier-template-validator.git
- [ ] Inspect af-fastapi and af-react fixture file shapes (need access to those repos)
- [ ] Confirm how `repeatable: true` deps name their answer files across components
