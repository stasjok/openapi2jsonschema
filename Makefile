.PHONY : test
test :
	pytest

.PHONY : lint
lint :
	black --check .

.PHONY : format
format :
	black .

.PHONY : deps
deps :
	pip install -r dev-dependencies.txt
