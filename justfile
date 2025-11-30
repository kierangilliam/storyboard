default:
    @just --list

run-example:
    uv run storyboard run --root-dir example

serve-example:
    uv run storyboard serve --scene-folder example/output

init-test:
    rm -rf test-project
    uv run storyboard init --name test-project
    cp .env test-project/.env

test:
    uv run pytest storyboard/tests/

build:
    rm -rf dist/
    uv run python -m build

publish:
    just build
    uv run twine upload dist/*

publish-test:
    uv run twine upload --repository testpypi dist/*
