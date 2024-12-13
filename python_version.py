from pathlib import Path
import yaml

# Create pipeline_results directory if it doesn't exist
results_dir = Path('pipeline_results')
results_dir.mkdir(exist_ok=True)

# First get linux and noarch packages from bioconda and conda-forge repos
linux_packages = set()
noarch_packages = set()

# Look in both bioconda-recipes and conda-forge directories
for repo in ['bioconda-recipes', 'conda-forge']:
    repo_path = Path(repo)
    if not repo_path.exists():
        print(f"Warning: {repo} repository not found at {repo_path}")
        continue

    print(f"Processing {repo}...")

    # Find linux-aarch64 packages
    for yaml_file in repo_path.rglob('*.yaml'):
        if yaml_file.is_file():
            try:
                content = yaml_file.read_text()
                if 'linux-aarch64' in content:
                    package = yaml_file.parts[2] if len(yaml_file.parts) > 2 else None
                    if package:
                        linux_packages.add(package)
                        if len(linux_packages) % 100 == 0:
                            print(f"Found {len(linux_packages)} linux packages...")
            except Exception as e:
                print(f"Error reading {yaml_file}: {e}")

    # Find noarch packages
    for yaml_file in repo_path.rglob('*.yaml'):
        if yaml_file.is_file() and 'ci_support' not in str(yaml_file):
            try:
                content = yaml_file.read_text()
                if 'noarch' in content:
                    if repo == 'bioconda-recipes':
                        package = yaml_file.parts[2] if len(yaml_file.parts) > 2 else None
                    else:  # conda-forge
                        package = yaml_file.parts[1].replace('-feedstock', '') if len(yaml_file.parts) > 1 else None
                    if package:
                        noarch_packages.add(package)
                        if len(noarch_packages) % 100 == 0:
                            print(f"Found {len(noarch_packages)} noarch packages...")
            except Exception as e:
                print(f"Error reading {yaml_file}: {e}")

print(f"Found {len(linux_packages)} linux packages and {len(noarch_packages)} noarch packages")

# For each pipeline, classify its packages and create a YAML file
for pipeline_dir in Path('pipelines').iterdir():
    if not pipeline_dir.is_dir():
        continue

    # Get all packages for this pipeline
    pipeline_packages = set()
    for env_file in pipeline_dir.glob("**/environment.yml"):
        try:
            with open(env_file) as f:
                env_data = yaml.safe_load(f)
                if env_data and 'dependencies' in env_data:
                    for dep in env_data['dependencies']:
                        if isinstance(dep, str) and '::' in dep:
                            # Parse package name, ignoring channel and version
                            package = dep.split('::')[1].split('=')[0].strip()
                            pipeline_packages.add(package)
        except Exception as e:
            print(f"Error processing {env_file}: {e}")

    # Classify packages
    arm_packages = pipeline_packages & linux_packages
    noarch_pkgs = pipeline_packages & noarch_packages
    unsupported = pipeline_packages - (linux_packages | noarch_packages)

    # Create YAML structure
    pipeline_data = {
        'arm_compatible': sorted(list(arm_packages)),
        'noarch': sorted(list(noarch_pkgs)),
        'unsupported': sorted(list(unsupported))
    }

    # Write YAML file
    yaml_path = results_dir / f"{pipeline_dir.name}.yaml"
    with open(yaml_path, 'w') as f:
        yaml.dump(pipeline_data, f, sort_keys=False)

    print(f"Created {yaml_path}")

print("\nAll pipeline YAML files have been created in the pipeline_results directory")

# After creating the YAML files, generate the summary report
print("\nGenerating report.md...")

with open('report.md', 'w') as f:
    # Write header
    f.write('| name | packages | packages_linux | packages_noarch | packages_missing |\n')
    f.write('|-|-|-|-|-|\n')

    # Process each pipeline's YAML file
    for yaml_file in sorted(results_dir.glob('*.yaml')):
        try:
            with open(yaml_file) as yf:
                data = yaml.safe_load(yf)

            pipeline_name = yaml_file.stem
            arm_count = len(data.get('arm_compatible', []))
            noarch_count = len(data.get('noarch', []))
            unsupported_count = len(data.get('unsupported', []))
            total_count = arm_count + noarch_count + unsupported_count

            # Write pipeline data
            f.write(f'|{pipeline_name}|{total_count}|{arm_count}|{noarch_count}|{unsupported_count}|\n')

        except Exception as e:
            print(f"Error processing {yaml_file}: {e}")

print("Report.md has been generated")

# Print final statistics
total_pipelines = len(list(results_dir.glob('*.yaml')))
print(f"\n=== Package Classification ===")
print(f"Total pipelines processed: {total_pipelines}")
print(f"Linux packages found: {len(linux_packages)}")
print(f"Noarch packages found: {len(noarch_packages)}")
