from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from tests.bootstrap import PROJECT_ROOT, SRC_ROOT


class ReleaseEnvResolverTests(unittest.TestCase):
    def test_resolver_derives_defaults_from_github_context(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "scripts/release/resolve_release_env.py",
                "--format",
                "json",
            ],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "GITHUB_REPOSITORY": "acme/nagient",
                "GITHUB_REPOSITORY_OWNER": "Acme",
            },
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(process.stdout)
        self.assertEqual(payload["project_slug"], "nagient")
        self.assertEqual(payload["default_channel"], "stable")
        self.assertEqual(payload["update_base_url"], "https://acme.github.io/nagient")
        self.assertEqual(payload["docker_image"], "docker.io/acme/nagient:0.1.0")
        self.assertEqual(payload["git_tag"], "v0.1.0")

    def test_resolver_uses_explicit_domain_and_registry_values(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "scripts/release/resolve_release_env.py",
                "--format",
                "json",
                "--version",
                "2.3.4",
            ],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "GITHUB_REPOSITORY": "acme/nagient",
                "GITHUB_REPOSITORY_OWNER": "Acme",
                "UPDATE_BASE_URL": "https://updates.your-domain.tld/agent",
                "CUSTOM_DOMAIN": "updates.your-domain.tld",
                "DOCKERHUB_NAMESPACE": "mydockerhub",
                "DOCKERHUB_IMAGE_NAME": "nagient-agent",
            },
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(process.stdout)
        self.assertEqual(payload["update_base_url"], "https://updates.your-domain.tld/agent")
        self.assertEqual(payload["custom_domain"], "updates.your-domain.tld")
        self.assertEqual(payload["docker_image"], "docker.io/mydockerhub/nagient-agent:2.3.4")
        self.assertEqual(
            payload["docker_image_latest"],
            "docker.io/mydockerhub/nagient-agent:latest",
        )


if __name__ == "__main__":
    unittest.main()
