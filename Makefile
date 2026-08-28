.PHONY: install test check run smoke

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
