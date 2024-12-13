import requests
from datetime import datetime

# URL of the JSON file
url = "https://nf-co.re/pipelines.json"

# Fetch the JSON data
response = requests.get(url)
pipelines = response.json()

# Filter pipelines with their first release in 2024
filtered_pipelines = []
for pipeline in pipelines["remote_workflows"]:
    releases = [r for r in pipeline.get("releases", []) if r.get("tag_name") != "dev"]
    if releases:
        # Sort releases by date to identify the first release
        sorted_releases = sorted(releases, key=lambda r: datetime.fromisoformat(r["published_at"]))
        first_release_date = datetime.fromisoformat(sorted_releases[0]["published_at"])
        if first_release_date.year == 2024:
            filtered_pipelines.append(pipeline["full_name"])

# Print the names of pipelines with their first release in 2024
print("Pipelines with their first release in 2024:")
for name in filtered_pipelines:
    print(name)
