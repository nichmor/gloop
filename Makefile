SHELL:=/usr/bin/env bash

.PHONY: test
test:
	poetry run pytest