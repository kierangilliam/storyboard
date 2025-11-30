import shutil
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

console = Console()


def init_command(args):
    project_name = args.name

    if not project_name:
        project_name = Prompt.ask("Enter project name")

    if not project_name or not project_name.strip():
        console.print("[red]Error: Project name cannot be empty[/red]")
        return 1

    project_name = project_name.strip()
    target_dir = Path.cwd() / project_name

    if target_dir.exists():
        console.print(f"[red]Error: Directory '{project_name}' already exists[/red]")
        return 1

    template_dir = Path(__file__).parent / "template"

    if not template_dir.exists():
        console.print(
            f"[red]Error: Template directory not found at {template_dir}[/red]"
        )
        return 1

    try:
        console.print(f"Creating project '{project_name}'...")

        shutil.copytree(
            template_dir,
            target_dir,
            ignore=shutil.ignore_patterns(
                "output", ".DS_Store", "__pycache__", "*.pyc"
            ),
        )

        console.print(
            f"[green]✓[/green] Project '{project_name}' created successfully!"
        )

        console.print(
            "\nGet your API key from: [blue]https://aistudio.google.com/app/apikey[/blue]"
        )
        api_key = Prompt.ask(
            "Enter your GEMINI_API_KEY (or press Enter to skip)", default=""
        )

        if api_key.strip():
            env_file = target_dir / ".env"
            with open(env_file, "w") as f:
                f.write(f"GEMINI_API_KEY={api_key.strip()}\n")
            console.print("[green]✓[/green] API key saved to .env")
            console.print("\nNext steps:")
            console.print(f"  1. cd {project_name}")
            console.print("  2. Run: storyboard run")
        else:
            console.print("\nNext steps:")
            console.print(f"  1. cd {project_name}")
            console.print("  2. cp .env.example .env")
            console.print("  3. Edit .env and add your GEMINI_API_KEY")
            console.print("  4. Run: storyboard run")

        return 0

    except Exception as e:
        console.print(f"[red]Error creating project: {e}[/red]")
        if target_dir.exists():
            shutil.rmtree(target_dir)
        return 1
