from __future__ import annotations

import json
import unittest

from tests.bootstrap import PROJECT_ROOT


class RepositoryContractTests(unittest.TestCase):
    def test_required_top_level_files_exist(self) -> None:
        required = [
            "README.md",
            "README.ru.md",
            "pyproject.toml",
            "Dockerfile",
            ".github/workflows/auto-tag.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".github/workflows/update-center.yml",
        ]
        for relative_path in required:
            self.assertTrue((PROJECT_ROOT / relative_path).exists(), msg=relative_path)

    def test_bundled_update_center_files_are_parseable(self) -> None:
        channel_payload = json.loads(
            (PROJECT_ROOT / "metadata/update-center/channels/stable.json").read_text(
                encoding="utf-8"
            )
        )
        release_payload = json.loads(
            (PROJECT_ROOT / "metadata/update-center/manifests/0.1.0.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(channel_payload["channel"], "stable")
        self.assertEqual(release_payload["version"], "0.1.0")

    def test_update_center_workflow_publishes_rendered_site_contract(self) -> None:
        update_center_workflow = (
            PROJECT_ROOT / ".github/workflows/update-center.yml"
        ).read_text(encoding="utf-8")
        release_workflow = (PROJECT_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("environment:", update_center_workflow)
        self.assertIn("name: github-pages", update_center_workflow)
        self.assertIn("render_bootstrap_assets.py", update_center_workflow)
        self.assertIn("peaceiris/actions-gh-pages@v4", update_center_workflow)
        self.assertIn("publish_branch: gh-pages", update_center_workflow)
        self.assertIn("Smoke check published bootstrap asset", update_center_workflow)
        self.assertNotIn("name: github-pages", release_workflow)
        self.assertNotIn("actions/deploy-pages", release_workflow)

    def test_auto_tag_workflow_dispatches_release_workflow(self) -> None:
        auto_tag_workflow = (PROJECT_ROOT / ".github/workflows/auto-tag.yml").read_text(
            encoding="utf-8"
        )
        release_workflow = (PROJECT_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("actions: write", auto_tag_workflow)
        self.assertIn("createWorkflowDispatch", auto_tag_workflow)
        self.assertIn("workflow_id: 'release.yml'", auto_tag_workflow)
        self.assertIn("workflow_dispatch:", release_workflow)

    def test_release_workflow_uses_dispatch_safe_docker_publish_gate(self) -> None:
        release_workflow = (PROJECT_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("id: docker_publish", release_workflow)
        self.assertIn("push_enabled=true", release_workflow)
        self.assertIn("steps.docker_publish.outputs.push_enabled", release_workflow)
        self.assertNotIn("if: ${{ secrets.DOCKERHUB_USERNAME", release_workflow)
        self.assertNotIn("push: ${{ secrets.DOCKERHUB_USERNAME", release_workflow)

    def test_release_workflow_publishes_multiarch_docker_images(self) -> None:
        release_workflow = (PROJECT_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("docker/setup-qemu-action@v3", release_workflow)
        self.assertIn("platforms: linux/amd64,linux/arm64", release_workflow)

    def test_workflows_opt_in_to_node_24_for_javascript_actions(self) -> None:
        for relative_path in [
            ".github/workflows/auto-tag.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".github/workflows/update-center.yml",
        ]:
            workflow = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: \"true\"", workflow)


if __name__ == "__main__":
    unittest.main()
