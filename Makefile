.PHONY: serve css css-watch test lint

serve: css  ## Run the e2e example server at http://localhost:8000
	PYTHONPATH=tests uv run django-admin runserver 8000 --settings=e2e.settings

css:  ## Build CSS from Tailwind source
	npx @tailwindcss/cli -i tests/e2e/app.css -o django_formwork/static/formwork/formwork-dist.css

css-watch:  ## Watch and rebuild CSS on changes
	npx @tailwindcss/cli -i tests/e2e/app.css -o django_formwork/static/formwork/formwork-dist.css --watch

test:  ## Run all tests (unit + e2e)
	uv run pytest tests/ -x -q

lint:  ## Run linters
	uv run ruff check && uv run ruff format --check
