install:
	poetry install

project:
	poetry run project

build:
	poetry build

publish:
	poetry publish --dry-run

package-install:
	python3 -m pip install dist/*.whl

lint:
	poetry run ruff check .

lint-fix:
	poetry run ruff check . --fix

test:
	python run_tests.py all

test-cli:
	python run_tests.py cli

test-core:
	python run_tests.py core

test-integration:
	python run_tests.py integration

test-quiet:
	python run_tests.py all --quiet

test-help:
	python run_tests.py help

test-count:
	python run_tests.py count