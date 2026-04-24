#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from nagient.cli import _build_release_manifest_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build release and channel manifests for Nagient.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--docker-image", required=True)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--summary", default="Automated release.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--channel-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = _build_release_manifest_payload(
        version=args.version,
        channel=args.channel,
        base_url=args.base_url,
        docker_image=args.docker_image,
        published_at=args.published_at,
        summary=args.summary,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if args.channel_output:
        channel_payload = {
            "channel": args.channel,
            "latest_version": args.version,
            "manifest_url": f"{args.base_url.rstrip('/')}/manifests/{args.version}.json",
            "published_at": args.published_at,
            "supported_installers": ["docker", "shell", "powershell"],
        }
        channel_path = Path(args.channel_output)
        channel_path.parent.mkdir(parents=True, exist_ok=True)
        channel_path.write_text(json.dumps(channel_payload, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
