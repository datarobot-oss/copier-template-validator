<p align="center">
  <a href="https://github.com/datarobot-oss/copier-template-validator">
    <img src="https://af.datarobot.com/img/datarobot_logo.avif" width="600px" alt="DataRobot Logo"/>
  </a>
</p>
<p align="center">
    <span style="font-size: 1.5em; font-weight: bold; display: block;">copier-template-validator</span>
</p>

<p align="center">
  <a href="https://datarobot.com">Homepage</a>
  ·
  <a href="https://af.datarobot.com">Documentation</a>
  ·
  <a href="https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html">Support</a>
</p>

<p align="center">
  <a href="https://github.com/datarobot-oss/copier-template-validator/tags">
    <img src="https://img.shields.io/github/v/tag/datarobot-oss/copier-template-validator?label=version" alt="Latest Release">
  </a>
  <a href="/LICENSE">
    <img src="https://img.shields.io/github/license/datarobot-oss/copier-template-validator" alt="License">
  </a>
  <a href="https://join.slack.com/t/datarobot-community/shared_invite/zt-3uzfp8k50-SUdMqeux25ok9_5wr4okrg">
    <img src="https://img.shields.io/badge/%23applications-a?label=Slack&labelColor=30373D&color=81FBA6" alt="Slack #applications">
  </a>
</p>

A GitHub Action that validates [Copier](https://copier.readthedocs.io) templates by automatically resolving their dependencies, rendering them, and running a suite of checks against the output.

This action is part of the [DataRobot App Framework](https://af.datarobot.com). It solves the problem of testing Copier templates that depend on other templates: rather than maintaining hand-written stub answer files, it dynamically renders each dependency in topological order to produce real answer files, then renders the target template on top of them.

# Table of contents

- [How it works](#how-it-works)
- [Usage](#usage)
- [Inputs](#inputs)
- [Requirements](#requirements)
- [Dependency resolution](#dependency-resolution)
- [Contributing, changelog, support, and legal](#contributing-changelog-support-and-legal)

# How it works

Every AF component is a Copier template — it cannot be run or tested directly. Before any checks can run, the template must be rendered. For templates that depend on other templates (via `copier-module.yaml`), those dependencies must be rendered first so their answer files are available.

This action automates the full sequence:

1. Reads `copier-module.yaml` from the target repo to discover dependencies
2. Clones each dependency and renders it with `--defaults` to produce real answer files
3. Uses topological sort to ensure dependencies are rendered in the correct order
4. Renders the target template with all answer files in place
5. The calling workflow then runs whatever checks it needs against the rendered output

# Usage

```yaml
jobs:
  validate:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/astral-sh/uv:python3.11-bookworm
    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Render template
        uses: datarobot-oss/copier-template-validator@main
        with:
          working-directory: .
          rendered-dir: ./rendered
          copier-args: '--data agent_template_framework=base'

      - name: Install dependencies
        working-directory: ./rendered/my_app
        run: uvx --from go-task-bin task install

      - name: Run tests
        working-directory: ./rendered/my_app
        run: uvx --from go-task-bin task test-coverage
```

The action only renders — all post-render steps are owned by the calling workflow, giving you named, individually-timed steps in the GitHub Actions UI.

# Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `working-directory` | No | `.` | Path to the template repo to validate (must contain `copier.yml`) |
| `copier-args` | No | `''` | Extra arguments passed to copier (e.g. `--data agent_template_framework=base`). `--defaults` is always added automatically. |
| `rendered-dir` | No | `./rendered` | Directory where the rendered template output will be written |

# Requirements

The action must run inside the `ghcr.io/astral-sh/uv` container image. This image provides `uv` and `uvx`, which are required for both the dependency resolver and the copier invocation.

```yaml
container:
  image: ghcr.io/astral-sh/uv:python3.11-bookworm
```

# Dependency resolution

Dependencies are declared in `copier-module.yaml` at the root of the template repo:

```yaml
module: af-component-agent
depends_on:
  base:
    url: https://github.com/datarobot-community/af-component-base
  llm:
    url: https://github.com/datarobot-community/af-component-llm
  mcp:
    url: https://github.com/datarobot-community/af-component-datarobot-mcp
```

The action reads this file, builds a dependency graph, and renders dependencies in topological order. For the example above:

```
af-base (no deps)     → renders first  → produces base.yml
af-llm  (needs base)  → renders second → produces llm-llm.yml
af-mcp  (needs base)  → renders second → produces drmcp-mcp_server.yml
af-component-agent    → renders last   → reads all three answer files
```

Each dependency is cloned at `HEAD` with `--depth=1` and rendered with `--defaults`. The resulting `.datarobot/answers/*.yml` file is placed where the target template expects it (read from `{dep}_answers_file` defaults in `copier.yml`).

# Contributing, changelog, support, and legal

See [LICENSE](LICENSE) for licensing information.

To contribute, fork the repository, make your changes on a branch, and open a pull request. Ensure the self-test workflow passes before submitting.

For support, [contact DataRobot](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html) or open an issue on the [GitHub repository](https://github.com/datarobot-oss/copier-template-validator).
