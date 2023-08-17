.PHONY: build

clean:
	@rm dist/*

build:
	@python3 -m build
