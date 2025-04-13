
format:
	isort .
	black .

check:
	mypy .


test:
	pytest tests/ -v --forked