from __future__ import annotations

import unittest
from pathlib import Path
import os
import subprocess
import tempfile


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
        private_provisioner = (
            project / "worker_environment/provision-private-local-worker.sh"
        ).read_text(encoding="utf-8")
        private_runner = (
            project / "worker_environment/run-private-local-sparkle.sh"
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
        self.assertIn("private local worker provisioning requires root", private_provisioner)
        self.assertIn("SPARKLE_EXTERNAL_WORKER_URL=https://localhost:8770/v1/jobs", private_provisioner)
        self.assertIn("SSL_CERT_FILE=$client_ca", private_provisioner)
        self.assertIn("install -o sparkle-worker -g sparkle-worker -m 0400", private_provisioner)
        self.assertIn("install -o \"$client_user\" -g \"$client_group\" -m 0600 \"$worker_signing_key\" \"$client_key\"", private_provisioner)
        self.assertNotIn("cat \"$worker_signing_key\"", private_provisioner)
        self.assertNotIn("echo $SPARKLE_WORKER_SIGNING_KEY", private_provisioner)
        self.assertIn("SPARKLE_EXTERNAL_WORKER_SIGNING_KEY_FILE=$client_key", private_provisioner)
        self.assertIn("export SPARKLE_EXTERNAL_WORKER_ID SPARKLE_EXTERNAL_WORKER_SIGNING_KEY_FILE SSL_CERT_FILE", private_runner)
        self.assertNotIn("SPARKLE_WORKER_SIGNING_KEY=$(cat", private_runner)
        self.assertNotIn("echo $SPARKLE_WORKER_SIGNING_KEY", private_runner)

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

    def test_private_local_runner_injects_secret_without_printing_it(self):
        project = Path(__file__).resolve().parents[1]
        runner = project / "worker_environment/run-private-local-sparkle.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / ".config" / "sparkle"
            config.mkdir(parents=True)
            key = config / "worker-signing-key"
            key.write_text("k" * 48, encoding="utf-8")
            key.chmod(0o600)
            ca = config / "worker-ca.crt"
            ca.write_text("public-test-ca", encoding="utf-8")
            env_file = config / "worker-client.env"
            env_file.write_text(
                "SPARKLE_EXTERNAL_WORKER_ENABLED=true\n"
                "SPARKLE_EXTERNAL_WORKER_URL=https://localhost:8770/v1/jobs\n"
                "SPARKLE_EXTERNAL_WORKER_ID=sparkle-level3-worker\n"
                f"SSL_CERT_FILE={ca}\n"
                f"SPARKLE_EXTERNAL_WORKER_SIGNING_KEY_FILE={key}\n",
                encoding="utf-8",
            )
            fake = root / "fake-sparkle"
            fake.write_text(
                "#!/bin/sh\n"
                "test \"$SPARKLE_EXTERNAL_WORKER_ENABLED\" = true\n"
                "test \"$SPARKLE_EXTERNAL_WORKER_URL\" = https://localhost:8770/v1/jobs\n"
                "test \"$SPARKLE_EXTERNAL_WORKER_SIGNING_KEY_FILE\" = \"$HOME/.config/sparkle/worker-signing-key\"\n"
                "test -z \"${SPARKLE_WORKER_SIGNING_KEY-}\"\n"
                "printf 'private-worker-configured\n'\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            environment = os.environ.copy()
            environment.pop("XDG_CONFIG_HOME", None)
            environment.update({"HOME": str(root), "SPARKLE_PRIVATE_CLI": str(fake)})
            completed = subprocess.run(
                [str(runner), "status"], env=environment, capture_output=True,
                text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "private-worker-configured")
            self.assertNotIn("k" * 48, completed.stdout + completed.stderr)



if __name__ == "__main__":
    unittest.main()
