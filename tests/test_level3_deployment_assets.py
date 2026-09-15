from __future__ import annotations

import unittest
from pathlib import Path


class Level3DeploymentAssetTests(unittest.TestCase):
    def test_all_runtime_surfaces_use_level3_worker_and_cancellation_route(self):
        project = Path(__file__).resolve().parents[1]
        pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
        dockerfile = (project / "worker_environment/Dockerfile").read_text(encoding="utf-8")
        compose = (project / "worker_environment/compose.yaml").read_text(encoding="utf-8")
        caddy = (project / "worker_environment/Caddyfile").read_text(encoding="utf-8")
        unit = (project / "worker_environment/sparkle-worker.service").read_text(encoding="utf-8")
        workflow = (project / ".github/workflows/level3-worker-acceptance.yml").read_text(encoding="utf-8")
        acceptance_doc = (project / "docs/LEVEL3_ACCEPTANCE.md").read_text(encoding="utf-8")
        readme = (project / "worker_environment/README.md").read_text(encoding="utf-8")
        makefile = (project / "Makefile").read_text(encoding="utf-8")
        installer = (
            project / "worker_environment/install-systemd-worker.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('sparkle-worker = "sparkle.level3_worker:entrypoint"', pyproject)
        self.assertNotIn('sparkle-worker = "sparkle.worker_service:entrypoint"', pyproject)
        self.assertIn('ENTRYPOINT ["python3", "-m", "sparkle.level3_worker"]', dockerfile)
        self.assertNotIn('ENTRYPOINT ["python3", "-m", "sparkle.worker_service"]', dockerfile)
        self.assertIn('"sparkle.level3_worker", "--check"', compose)
        self.assertNotIn('"sparkle.worker_service", "--check"', compose)
        self.assertIn("/v1/jobs/cancel", caddy)
        self.assertIn("handle @jobs {", caddy)
        self.assertIn("reverse_proxy worker:8770", caddy)
        self.assertIn("handle {\n        respond 404\n    }", caddy)
        self.assertNotIn("reverse_proxy @jobs worker:8770", caddy)
        self.assertIn("ExecStart=/opt/sparkle/.venv/bin/sparkle-worker", unit)
        self.assertIn("python3 -m sparkle.level3_worker --check", readme)
        self.assertNotIn("python3 -m sparkle.worker_service --check", readme)
        self.assertIn("worker-check:\n\tPYTHONPATH=src python3 -m sparkle.level3_worker --check", makefile)
        self.assertIn("worker-diagnose:\n\tPYTHONPATH=src python3 -m sparkle.level3_worker --diagnose", makefile)
        self.assertIn("worker-dev:\n\tPYTHONPATH=src SPARKLE_WORKER_EXECUTOR=process SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR=true python3 -m sparkle.worker_service", makefile)
        self.assertIn("--upgrade --force-reinstall", installer)
        self.assertNotIn("sudo -u sparkle-worker /opt/sparkle/.venv/bin/sparkle-worker --check", installer)
        self.assertNotIn("sudo -u sparkle-worker /opt/sparkle/.venv/bin/sparkle-worker --check", readme)
        self.assertIn("sudo systemctl start sparkle-worker", installer)
        self.assertIn("http://127.0.0.1:8770/health", installer)
        self.assertIn("http://127.0.0.1:8770/health", readme)

        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("vars.SPARKLE_EXTERNAL_WORKER_URL", workflow)
        self.assertIn("vars.SPARKLE_EXTERNAL_WORKER_ID", workflow)
        self.assertIn("secrets.SPARKLE_WORKER_SIGNING_KEY", workflow)
        self.assertIn("level3_remote_probe.py", workflow)
        self.assertIn("worker_environment.level3_lifecycle_probe", workflow)
        self.assertIn("worker_environment.level3_full_acceptance", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("if: always()", workflow)

        self.assertIn("SPARKLE_EXTERNAL_WORKER_URL", acceptance_doc)
        self.assertIn("SPARKLE_EXTERNAL_WORKER_ID", acceptance_doc)
        self.assertIn("SPARKLE_WORKER_SIGNING_KEY", acceptance_doc)
        self.assertIn("worker interruption/recovery", acceptance_doc)
        self.assertIn("Deployment remains frozen", acceptance_doc)


if __name__ == "__main__":
    unittest.main()
