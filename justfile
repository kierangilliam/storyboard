default:
    @just --list

run-example:
    uv run storyboard run --input content/main.yaml --output output --root-dir example

test:
    uv run pytest storyboard/tests/
