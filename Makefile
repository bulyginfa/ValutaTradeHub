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

clean:
	rm -rf dist/ build/ *.egg-info/

reinstall: clean
	python3 -m pip uninstall finalproject-bulygin-m25-555 -y || true
	make build
	make package-install