.PHONY: build deps clean build test check test-release release

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
	@pytest -q

check:
	@twine check dist/*
	./hack/check-releasable.sh

test-release: check
	@twine upload -r testpypi dist/*

release: 
	@twine upload -r pypi dist/*
