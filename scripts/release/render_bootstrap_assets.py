#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_TEMPLATES = {
    "scripts/bootstrap/install.sh": "install.sh",
    "scripts/bootstrap/install.ps1": "install.ps1",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render bootstrap install assets for the update center root."
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--update-base-url", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    replacements = {
        "__NAGIENT_UPDATE_BASE_URL__": args.update_base_url.rstrip("/"),
    }

    for source_path, target_name in _TEMPLATES.items():
        template_path = REPO_ROOT / source_path
        rendered = template_path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)

        target_path = output_dir / target_name
        target_path.write_text(rendered, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
