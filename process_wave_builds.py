#!/usr/bin/env python3

import yaml
import subprocess
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from pathlib import Path
import concurrent.futures
from threading import Lock
import argparse

console = Console()
progress_lock = Lock()


def run_wave_command(package, progress, task_id):
    """Run wave command for a package and return status and image URL if successful"""

    # Strip the version from the package
    package = package.split('=')[0]
    # Remove trailing > or < characters
    package = package.rstrip('>').rstrip('<')

    # Try bioconda first
    try:
        # Skip bioconda for specific packages
        assert package not in [
            'tar',
            'sed',
            'grep',
            'gawk',
            'p7zip',
            'requests',
            'pigz',
            'python',
            'pygments',
            'markdown',
            'pandas',
            'numpy',
            'openjdk',
            'r-base',
            'coreutils',
            'biopython',
            'pymdown-extensions',
            'libiconv'
        ]

        # Skip conda-forge packages
        assert 'conda-forge::' not in package

        command = ['wave', '--conda', f'bioconda::{package}', '--platform', 'linux/arm64', '--freeze', '--await']
        with progress_lock:
            # console.print(f"[cyan]Running:[/cyan] {' '.join(command)}")
            pass

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        with progress_lock:
            progress.update(task_id, advance=1)
            # console.print(f"[green]✓[/green] Package '{package}' build successful: [dim]{result.stdout.strip()}[/dim]")
        return package, True, result.stdout.strip()
    except (subprocess.CalledProcessError, AssertionError) as bioconda_error:
        error_msg = None
        # Clean up + log error message if it's a Wave build error
        if isinstance(bioconda_error, subprocess.CalledProcessError):
            error_msg = bioconda_error.stderr.strip()
            if "Container provisioning did not complete successfully" in error_msg:
                build_id = error_msg.split('/')[-1]
                error_msg = f"Container provisioning failed, see https://wave.seqera.io/view/builds/{build_id}"
            with progress_lock:
                # console.print(f"[red]Bioconda build failed for '{package}':[/red] [dim red]{error_msg}[/dim red]")
                pass
            # Exit immediately if we've hit the rate limit
            if "Request exceeded build rate limit" in error_msg:
                console.print("[red]Rate limit exceeded, exiting[/red]")
                exit(1)

        # Try conda-forge
        try:
            command = ['wave', '--conda', f'{package}', '--platform', 'linux/arm64', '--freeze', '--await']
            with progress_lock:
                # console.print(f"[yellow]Retrying with conda-forge:[/yellow] {' '.join(command)}")
                pass

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            with progress_lock:
                progress.update(task_id, advance=1)
                # console.print(f"[green]✓[/green] Package '{package}' build successful with conda-forge: [dim]{result.stdout.strip()}[/dim]")
            return package, True, result.stdout.strip()
        except subprocess.CalledProcessError as conda_forge_error:
            # Exit immediately if we've hit the rate limit
            if "Request exceeded build rate limit" in conda_forge_error.stderr:
                console.print("[red]Rate limit exceeded, exiting[/red]")
                exit(1)
            if error_msg is None:
                error_msg = conda_forge_error.stderr.strip()
            with progress_lock:
                progress.update(task_id, advance=1)
                # console.print(f"[red]✗[/red] Package '{package}' build failed on both channels")
            # Return the original bioconda error for the results table
            return package, False, error_msg


def main():
    # Add argument parser
    parser = argparse.ArgumentParser(description='Process Wave builds for pipeline packages')
    parser.add_argument('--all', action='store_true', help='Process all pipelines without prompts')
    parser.add_argument('--pipeline', help='Process a specific pipeline without prompts')
    args = parser.parse_args()

    # If --all flag is used, skip the prompt
    if args.all:
        run_all = "y"
    # If --pipeline is specified, process just that pipeline
    elif args.pipeline:
        process_pipeline(args.pipeline)
        return
    else:
        # Original interactive prompt
        run_all = Prompt.ask("Process all pipelines?", choices=["y", "n"], default="n")

    if run_all == "y":
        # Read pipeline names from file
        with open("pipelines_by_stars.txt", "r") as f:
            pipeline_names = [line.strip() for line in f if line.strip()]

        console.print(f"\n[bold blue]Found {len(pipeline_names)} pipelines to process[/bold blue]\n")

        # Process each pipeline with index
        for idx, pipeline_name in enumerate(pipeline_names, 1):
            # Check if results file already exists
            results_file = Path('wave_results') / f"{idx:03d}_{pipeline_name}.yaml"
            if results_file.exists():
                console.print(f"[yellow]Skipping pipeline {idx}/{len(pipeline_names)}: {pipeline_name} - results already exist[/yellow]")
                continue

            console.print(f"\n[bold cyan]Processing pipeline {idx}/{len(pipeline_names)}: {pipeline_name}[/bold cyan]")
            process_pipeline(pipeline_name, idx)
    else:
        # Original single pipeline logic
        pipeline_name = Prompt.ask("Enter pipeline name")
        process_pipeline(pipeline_name)


def process_pipeline(pipeline_name, idx=None):
    """Extract existing pipeline processing logic into separate function"""
    yaml_path = Path(f"pipeline_conda_packages/{pipeline_name}.yaml")

    if not yaml_path.exists():
        console.print(f"[red]Error: {yaml_path} not found!")
        return

    # Load YAML file
    with open(yaml_path) as f:
        all_packages = yaml.safe_load(f)

    # Add total packages log message
    # console.print(f"\n[bold blue]Found {len(all_packages)} packages to process[/bold blue]\n")

    results = {}
    max_workers = min(50, len(all_packages))  # Limit max concurrent jobs

    # Create progress bar with custom columns
    progress = Progress(
        SpinnerColumn(),
        TextColumn(f"[progress.description]'{pipeline_name}' - {len(all_packages)} packages"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    )

    with progress:
        # Add main progress task
        task_id = progress.add_task(
            description="[cyan]Building containers...",
            total=len(all_packages)
        )

        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_package = {
                executor.submit(run_wave_command, package, progress, task_id): package
                for package in all_packages
            }

            # Process completed tasks
            for future in concurrent.futures.as_completed(future_to_package):
                package, success, output = future.result()
                results[package] = {
                    'success': success,
                    'output': output
                }

    # Calculate summary
    success_count = sum(1 for r in results.values() if r['success'])
    fail_count = len(results) - success_count
    success_percent = (success_count / len(results)) * 100 if results else 0

    # Update summary markdown file
    summary_file = Path('wave_results/00_summary.md')
    if not summary_file.parent.exists():
        summary_file.parent.mkdir(parents=True)

    # Create file with headers if it doesn't exist
    if not summary_file.exists():
        with open(summary_file, 'w') as f:
            f.write("| Pipeline | Success % | Succeeded | Failed |\n")
            f.write("|----------|-----------|-----------|--------|\n")

    # Append pipeline results
    with open(summary_file, 'a') as f:
        f.write(f"| {pipeline_name} | {success_percent:.1f}% | {success_count} | {fail_count} |\n")

    # Display summary
    console.print("\n[bold green]Build Summary:")
    console.print(f"Successful builds: {success_count}")
    console.print(f"Failed builds: {fail_count}")

    # Create and display results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Package")
    table.add_column("Status")
    table.add_column("Output")

    # Sort results by success status first, then by package name
    sorted_results = sorted(
        results.items(),
        key=lambda x: (not x[1]['success'], x[0])  # Sort by success (True first) then package name
    )

    for package, result in sorted_results:
        status = "[green]Success" if result['success'] else "[red]Failed"
        output = result['output']
        # Clean up error message for the table if it's a failed build
        if not result['success'] and "Container provisioning did not complete successfully" in output:
            build_id = output.split('/')[-1]
            output = f"Container provisioning failed, see https://wave.seqera.io/view/builds/{build_id}"
        table.add_row(
            package,
            status,
            output
        )

    console.print(f"\n[bold]Detailed Results for '{pipeline_name}':")
    console.print(table)

    # Save results to YAML file
    wave_results_dir = Path('wave_results')
    wave_results_dir.mkdir(exist_ok=True)

    yaml_results = {
        'passed': [
            {package: result['output']}
            for package, result in sorted_results
            if result['success']
        ],
        'failed': [
            {package: result['output']}
            for package, result in sorted_results
            if not result['success']
        ]
    }
    # Add index prefix to filename if idx is provided
    filename = f"{pipeline_name}.yaml"
    if idx is not None:
        filename = f"{idx:03d}_{filename}"

    results_file = wave_results_dir / filename
    with open(results_file, 'w') as f:
        yaml.dump(yaml_results, f, sort_keys=False)

    console.print(f"\n[bold green]Results saved to {results_file}")


if __name__ == "__main__":
    main()