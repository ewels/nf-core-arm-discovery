# Clone pipeline repos
cd pipelines
for pipeline in $(cat pipeline_names.txt)
do
gh repo clone nf-core/${pipeline}
done
cd ..

# Clone bioconda recipes
gh repo clone bioconda/bioconda-recipes

# Clone conda-forge recipes
gh repo clone conda-forge/feedstocks
