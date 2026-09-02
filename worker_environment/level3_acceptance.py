"""Run the external worker boundary gate without changing SPARKLE state.

This probe is infrastructure-dependent. A pass proves only the named worker's
authenticated Bubblewrap boundary. The full Level 3 gate still requires an
approved immutable artifact through ControlledExecutionService.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from sparkle.external_worker import ExternalWorkerClient, ExternalWorkerError


def main() -> int:
    endpoint = os.environ.get("SPARKLE_EXTERNAL_WORKER_URL", "").strip()
    worker_id = os.environ.get("SPARKLE_EXTERNAL_WORKER_ID", "").strip()
    with tempfile.TemporaryDirectory(prefix="sparkle-level3-acceptance-") as directory:
        root = Path(directory)
        workspace = root / "workspace"
        (workspace / "tests").mkdir(parents=True)
        source = b"READY = True\n"
        test = (
            b"import unittest\nfrom main import READY\n\n"
            b"class BoundaryReady(unittest.TestCase):\n"
            b"    def test_ready(self): self.assertTrue(READY)\n"
        )
        (workspace / "main.py").write_bytes(source)
        (workspace / "tests/test_boundary.py").write_bytes(test)
        artifact_digest = hashlib.sha256(source + test).hexdigest()
        client = ExternalWorkerClient(
            root=root,
            path=root / "acceptance.sqlite3",
            enabled=True,
            endpoint=endpoint,
            expected_worker_id=worker_id,
        )
        context = {
            "execution_id": "SPK-EXEC-" + "1" * 32,
            "execution_request_id": "SPK-EXEC-REQ-" + "2" * 32,
            "artifact_id": 1,
            "artifact_sha256": artifact_digest,
            "build_id": "SPK-BUILD-LEVEL3-ACCEPTANCE",
            "promotion_id": "SPK-PROMO-LEVEL3-ACCEPTANCE",
            "candidate_id": 1,
            "plan_id": 1,
            "evaluation_id": "SPK-EVAL-LEVEL3-ACCEPTANCE",
            "authorization_id": "SPK-EXEC-AUTH-LEVEL3-ACCEPTANCE",
            "execution_mode": "python_unittest",
        }
        result = client.run_controlled_execution(
            "level3_worker_acceptance",
            workspace,
            execution_context=context,
            timeout_seconds=10,
            max_output_chars=4_000,
        )
        evidence = {
            "gate": "SPARKLE-LEVEL3-WORKER-BOUNDARY/1",
            "worker_id": result["worker_id"],
            "job_id": result["job_id"],
            "artifact_sha256": artifact_digest,
            "response_verified": result["response_verified"],
            "isolation_verified": result["isolation_verified"],
            "isolation_evidence": result["isolation_evidence"],
            "result_digest": result["result_digest"],
            "started_at": result["started_at"],
            "completed_at": result["completed_at"],
            "level_3_complete": False,
            "requires_approved_artifact_followup": True,
        }
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0 if (
            result["response_verified"] and result["isolation_verified"]
        ) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExternalWorkerError, ValueError) as exc:
        print(json.dumps({
            "gate": "SPARKLE-LEVEL3-WORKER-BOUNDARY/1",
            "status": "blocked",
            "error_type": type(exc).__name__,
            "isolation_verified": False,
            "level_3_complete": False,
        }, indent=2, sort_keys=True))
        raise SystemExit(1) from None
