.PHONY : test
test :
	pytest

.PHONY : lint
lint :
	black --diff .
	isort --diff .

.PHONY : format
format :
	black .
	isort .

.PHONY : deps
deps :
	pip install -r dev-dependencies.txt
