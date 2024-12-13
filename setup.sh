# Clone pipeline repos
cd pipelines
for pipeline in $(cat pipeline_names.txt)
do
    gh repo clone nf-core/${pipeline} -- --branch dev --depth 1
done
cd ..
