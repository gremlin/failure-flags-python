.PHONY: build

clean:
	@rm dist/*
	@rm -rf build/*

build:
	@python3 -m build
	@python3 -m pip install -e .

test:
	@pytest -q

check:
	@twine check dist/*

release: build check
	@twine upload -r testpypi dist/*

