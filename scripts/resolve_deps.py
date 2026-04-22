#!/usr/bin/env python3
"""
resolve_deps.py

Reads copier-module.yaml from a template repo, dynamically renders each
dependency in topological order to produce real answer files, then renders
the target template with those answer files in place.

Usage:
    python3 resolve_deps.py \
        --template-dir /path/to/template \
        --rendered-dir /path/to/output \
        --copier-args "--data agent_template_framework=base"
"""
import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def read_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get_answers_file_default(copier_yml: dict, dep_key: str) -> str | None:
    """
    Given a copier.yml dict and a dependency key (e.g. "llm"),
    return the default value for {dep_key}_answers_file question.
    e.g. ".datarobot/answers/llm-llm.yml"
    """
    question_key = f"{dep_key}_answers_file"
    question = copier_yml.get(question_key)
    if question is None:
        return None
    default = question.get("default") if isinstance(question, dict) else question
    return default


def find_rendered_answers_file(rendered_dir: Path) -> Path | None:
    """
    After rendering a dep, find the answers file it produced under
    .datarobot/answers/. Each dep produces exactly one answers file.
    """
    answers_dir = rendered_dir / ".datarobot" / "answers"
    if not answers_dir.exists():
        return None
    files = list(answers_dir.glob("*.yml"))
    if not files:
        return None
    if len(files) > 1:
        print(f"Warning: found {len(files)} answer files in {answers_dir}, using {files[0].name}")
    print(f"  Found answers file: {files[0].name}")
    return files[0]


def topo_sort(deps: dict[str, dict], dep_trees: dict[str, list[str]]) -> list[str]:
    """
    Topological sort of dep keys given their own sub-dependencies.
    dep_trees: { "llm": ["base"], "mcp": ["base"], "base": [] }
    Returns ordered list e.g. ["base", "llm", "mcp"]
    """
    visited = set()
    order = []

    def visit(key: str) -> None:
        if key in visited:
            return
        visited.add(key)
        for sub in dep_trees.get(key, []):
            visit(sub)
        order.append(key)

    for key in deps:
        visit(key)

    return order


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve deps and render a copier template")
    parser.add_argument("--template-dir", required=True, type=Path)
    parser.add_argument("--rendered-dir", required=True, type=Path)
    parser.add_argument("--copier-args", default="", type=str)
    args = parser.parse_args()

    template_dir = args.template_dir.resolve()
    rendered_dir = args.rendered_dir.resolve()
    extra_copier_args = shlex.split(args.copier_args)

    # Always ensure --defaults is present, but never duplicated
    if "--defaults" not in extra_copier_args:
        extra_copier_args = ["--defaults"] + extra_copier_args

    module_yaml_path = template_dir / "copier-module.yaml"
    copier_yml_path = template_dir / "copier.yml"

    # No copier-module.yaml → render directly with no dep resolution
    if not module_yaml_path.exists():
        print("No copier-module.yaml found, rendering directly.")
        rendered_dir.mkdir(parents=True, exist_ok=True)
        run(["uvx", "copier", "copy", str(template_dir), str(rendered_dir), "--overwrite"] + extra_copier_args)
        return

    module = read_yaml(module_yaml_path)
    deps = module.get("depends_on", {})

    if not deps:
        print("No dependencies found in copier-module.yaml, rendering directly.")
        rendered_dir.mkdir(parents=True, exist_ok=True)
        run(["uvx", "copier", "copy", str(template_dir), str(rendered_dir), "--overwrite"] + extra_copier_args)
        return

    copier_yml = read_yaml(copier_yml_path) if copier_yml_path.exists() else {}

    # Build dep trees for topo sort by cloning each dep briefly
    # We use a tmp dir for all intermediate work
    tmp_dir = Path(tempfile.mkdtemp(prefix="ctv-"))
    print(f"Working directory: {tmp_dir}")

    try:
        # Pass 1: collect sub-deps of each dep (for topo sort)
        dep_trees: dict[str, list[str]] = {}
        for dep_key, dep_info in deps.items():
            dep_url = dep_info["url"]
            probe_dir = tmp_dir / f"{dep_key}-probe"
            run(["git", "clone", "--depth=1", "--filter=blob:none", dep_url, str(probe_dir)])
            probe_module = probe_dir / "copier-module.yaml"
            if probe_module.exists():
                sub = read_yaml(probe_module).get("depends_on", {})
                # Only include sub-deps that are also in our top-level deps
                dep_trees[dep_key] = [k for k in sub if k in deps]
            else:
                dep_trees[dep_key] = []

        # Topo sort
        sorted_deps = topo_sort(deps, dep_trees)
        print(f"Render order: {sorted_deps}")

        # Pass 2: render each dep in order
        # already_rendered maps dep_key → path of its produced answers file
        already_rendered: dict[str, Path] = {}

        for dep_key in sorted_deps:
            dep_url = deps[dep_key]["url"]
            print(f"\n── Rendering dep: {dep_key} ({dep_url})")

            # Reuse the probed clone dir rather than cloning again
            clone_dir = tmp_dir / f"{dep_key}-probe"
            dep_rendered_dir = tmp_dir / f"{dep_key}-rendered"
            dep_rendered_dir.mkdir(parents=True, exist_ok=True)

            # Place sub-dep answer files before rendering
            dep_copier_yml_path = clone_dir / "copier.yml"
            if dep_copier_yml_path.exists():
                dep_copier_yml = read_yaml(dep_copier_yml_path)
                dep_module_yaml = clone_dir / "copier-module.yaml"
                sub_deps = read_yaml(dep_module_yaml).get("depends_on", {}) if dep_module_yaml.exists() else {}

                for sub_key in sub_deps:
                    if sub_key not in already_rendered:
                        continue
                    sub_answers_default = get_answers_file_default(dep_copier_yml, sub_key)
                    if sub_answers_default is None:
                        continue
                    dest = dep_rendered_dir / sub_answers_default
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(already_rendered[sub_key], dest)
                    print(f"  Placed {sub_key} answers at {dest}")

            # Render the dep
            run(["uvx", "copier", "copy", str(clone_dir), str(dep_rendered_dir), "--defaults", "--overwrite"])

            # Find the answers file it produced
            answers_file = find_rendered_answers_file(dep_rendered_dir)
            if answers_file is None:
                print(f"Warning: no answers file found after rendering {dep_key}")
                continue

            already_rendered[dep_key] = answers_file
            print(f"  Produced answers: {answers_file.name}")

        # Place all dep answer files into the rendered-dir before main render
        rendered_dir.mkdir(parents=True, exist_ok=True)
        for dep_key, answers_file in already_rendered.items():
            dest_relative = get_answers_file_default(copier_yml, dep_key)
            if dest_relative is None:
                # Fall back to placing it at the same relative path it was written to
                dest_relative = str(answers_file.relative_to(tmp_dir / f"{dep_key}-rendered"))
            dest = rendered_dir / dest_relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(answers_file, dest)
            print(f"Placed {dep_key} answers → {dest}")

        # Final render of the main template
        print(f"\n── Rendering main template: {template_dir}")
        run(
            ["uvx", "copier", "copy", str(template_dir), str(rendered_dir), "--overwrite"]
            + extra_copier_args
        )

        print(f"\n✓ Rendered to {rendered_dir}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
