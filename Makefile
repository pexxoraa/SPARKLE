.PHONY: install test check run smoke worker-check worker-dev

install:
	python3 -m pip install -e .

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

check:
	python3 -m compileall -q src tests
	PYTHONPATH=src python3 -m unittest discover -s tests -v

run:
	PYTHONPATH=src python3 -m sparkle serve

smoke:
	PYTHONPATH=src python3 -m sparkle smoke-test --live

worker-check:
	PYTHONPATH=src python3 -m sparkle.worker_service --check

worker-dev:
	PYTHONPATH=src SPARKLE_WORKER_EXECUTOR=process SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR=true python3 -m sparkle.worker_service
