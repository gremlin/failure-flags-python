.PHONY: build deps clean build test check check-package check-releasable test-release release

deps:
	@pip install pytest twine pip-tools

clean:
	@ls -al dist
	@rm dist/*
	@rm -rf build/*

build:
	@python3 -m build
	@python3 -m pip install -e .
	@./hack/version-alignment-check.sh

test:
	@pytest -q --junitxml=/tmp/failure-flags-python.junit.xml

check-package:
	@twine check dist/*

check-releasable:
	@./hack/check-releasable.sh

check: check-package check-releasable

test-release: check-package
	@twine upload --verbose -r testpypi dist/*

release: 
	@twine upload -r pypi dist/*
