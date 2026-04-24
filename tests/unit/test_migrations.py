from __future__ import annotations

import unittest

from nagient.domain.entities.release import MigrationStep
from nagient.domain.versioning import Version
from nagient.migrations.planner import plan_migrations


class MigrationPlannerTests(unittest.TestCase):
    def test_plans_linear_migration_chain(self) -> None:
        steps = [
            MigrationStep(
                step_id="one",
                from_version=Version.parse("0.1.0"),
                to_version=Version.parse("0.2.0"),
                description="step one",
                command="cmd one",
            ),
            MigrationStep(
                step_id="two",
                from_version=Version.parse("0.2.0"),
                to_version=Version.parse("0.3.0"),
                description="step two",
                command="cmd two",
            ),
        ]

        planned = plan_migrations(
            current_version=Version.parse("0.1.0"),
            target_version=Version.parse("0.3.0"),
            candidates=steps,
        )

        self.assertEqual([step.step_id for step in planned], ["one", "two"])

    def test_ignores_unrelated_steps(self) -> None:
        steps = [
            MigrationStep(
                step_id="other",
                from_version=Version.parse("0.4.0"),
                to_version=Version.parse("0.5.0"),
                description="unrelated",
                command="noop",
            )
        ]

        planned = plan_migrations(
            current_version=Version.parse("0.1.0"),
            target_version=Version.parse("0.3.0"),
            candidates=steps,
        )

        self.assertEqual(planned, [])


if __name__ == "__main__":
    unittest.main()
