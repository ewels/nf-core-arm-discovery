from pathlib import Path
import yaml
import re

# Create pipeline_results directory if it doesn't exist
results_dir = Path('pipeline_conda_packages')
results_dir.mkdir(exist_ok=True)

# For each pipeline, classify its packages and create a YAML file
for pipeline_dir in Path('pipelines').iterdir():
    if not pipeline_dir.is_dir():
        continue

    # Look in environment.yml files
    pipeline_packages = set()
    for env_file in pipeline_dir.glob("**/environment.yml"):
        try:
            with open(env_file) as f:
                env_data = yaml.safe_load(f)
                if env_data and 'dependencies' in env_data:
                    for dep in env_data['dependencies']:
                        if isinstance(dep, str):
                            # Remove 'bioconda::' prefix if present
                            pipeline_packages.add(dep.replace('bioconda::', ''))
        except Exception as e:
            print(f"Error processing {env_file}: {e}")

    # Look in main.nf conda declarations
    for mod_file in pipeline_dir.glob("**/main.nf"):
        try:
            with open(mod_file) as f:
                content = f.read()
                # Look for conda declarations including conditional syntax
                conda_matches = re.finditer(r"^\s*conda\s*(?:\(.*\?\s*)?['\"]([^'\"\n]+)['\"]", content, re.MULTILINE)
                for match in conda_matches:
                    if 'environment.yml' not in match.group(1):
                        # Split by whitespace and process each package separately
                        packages = match.group(1).split()
                        for package in packages:
                            # Remove 'bioconda::' prefix if present
                            package = package.replace('bioconda::', '')
                            pipeline_packages.add(package)
        except Exception as e:
            print(f"Error processing {mod_file}: {e}")

    # Write YAML file
    yaml_path = results_dir / f"{pipeline_dir.name}.yaml"
    with open(yaml_path, 'w') as f:
        yaml.dump(list(pipeline_packages), f)

    print(f"Found {len(pipeline_packages)} packages for {pipeline_dir.name}")

