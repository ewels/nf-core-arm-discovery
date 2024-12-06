# functions that are used later (find files, find content)
f(){ echo find -iname "'*$1*'" | bash ; }
F(){
    [ $# = 1 ] && grep -Rin "$1" ;
    [ $# = 2 ] && grep -Rin "$1" $( find -iname "*.$2" );
}

# execute in a folder with the nf-pipelines downloaded to obtain its dependencies
for a in pipelines/*
do
    cd $a;
    (
        f environment.yml | \
            xargs cat | \
            grep :: | \
            sed -e 's/::/@/g' -e 's/=/@/g' -e 's/</@/g' -e 's/>/@/g' | \
            cut -d@ -f2 | \
            sort -u;
        F conda | \
            grep :: | \
            sed -e 's/"/ /g' | \
            sed 's/ /\n/g' | \
            grep '\(bioconda\|conda-forge\)' | \
            sed -e 's/::/@/g' -e 's/=/@/g' -e 's/</@/g' -e 's/>/@/g' | \
            cut -d@ -f2 | \
            sort -u
    ) | \
    sort -u | \
    grep -v 'http://' | \
    grep -v 'mulled' | \
    sed 's/:.*//g' | \
    tee packages
    cd ..
done

# execute in the bioconda-recipes and conda-forge folders to obtain list of linux and noarch packages
for d in {bioconda-recipes,conda-forge}
do
    cd $d
    F linux-aarch64 yaml | \
        cut -d/ -f3 | \
        sort -u > packages_linux
    F noarch yaml | \
        cut -d/ -f3 | \
        sort -u > packages_noarch
    F noarch yaml | \
        grep -v ci_support | \
        cut -d/ -f2 | \
        sort -u | \
        sed 's/-feedstock//g' > packages_noarch
    cd ..
done

# execute in the folder with the nf-pipelines downloaded to classify its dependencies
for a in pipelines/*
do
    cd $a
    comm -12 <(cat packages | sort -u) <(cat ../{bioconda-recipes,conda-forge}/packages_linux | sort -u) > packages_linux
    cd ..
done
for a in *
do
    cd $a
    comm -12 <(cat packages | sort -u) <(cat ../{bioconda-recipes,conda-forge}/packages_noarch | sort -u) > packages_noarch
    cd ..
done
for a in *
do
    cd $a
    comm -23 <(cat packages | sort -u) <(cat ../{bioconda-recipes,conda-forge}/packages_{linux,noarch} | sort -u) > packages_missing
    cd ..
done

# generate final report
(
    echo "| name | packages | packages_linux | packages_noarch | packages_missing |" \
    echo "|-|-|-|-|-|" \
    for a in *
    do
        cd $a
        echo "$a | $(cat packages | wc -l) | $(cat packages_linux | wc -l) | $(cat packages_noarch | wc -l) | $(cat packages_missing | wc -l) |"
        cd ..
    done
) > /tmp/final
