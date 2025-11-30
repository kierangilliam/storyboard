default:
    @just --list

cu:
    claude --allowedTools mcp__container-use__environment_checkpoint,mcp__container-use__environment_create,mcp__container-use__environment_add_service,mcp__container-use__environment_file_delete,mcp__container-use__environment_file_list,mcp__container-use__environment_file_read,mcp__container-use__environment_file_write,mcp__container-use__environment_open,mcp__container-use__environment_run_cmd,mcp__container-use__environment_update

generate-example:
    uv run storyboard generate --root-dir example

serve-example:
    uv run storyboard serve --scene-folder example/output

update-example:
    uv run storyboard update --root-dir example

composite-example:
    uv run storyboard composite movie --scene-folder example/output --input example/content/main.yaml

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
