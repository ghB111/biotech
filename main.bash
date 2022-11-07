#!/usr/bin/env bash 

if [ "$#" -ne 2 ]; then
    printf "Usage: ./main.bash reference.fa.gz sequence.fastq.gz \nMake sure not to give absolute paths\nMake sure bwa, samtools are in path\n"
    exit 111
fi

reference="$1"
sequence="$2"
tmp_dir="./tmp"

mkdir -p "./tmp"

if ! cp "$reference" "$tmp_dir"; then echo "Could not copy reference" ; exit 1; fi
if ! cp "$sequence"  "$tmp_dir"; then echo "Could not copy sequence" ; exit 1; fi

pushd "$tmp_dir"

bwa index "$reference"
bwa mem "$reference" "$sequence" > res.sam 

samtools view --bam ./res.sam > res.bam 
printf "\nDoing samtools flagstat and grepping result. OK means >90%%, BAD! means <90%%\n\n"
samtools flagstat res.bam | grep mapped | head -n 1 | awk '{print substr($5, 2, length($5)-2)}' | awk '{if ($1>90) print "OK:" $1; else print "BAD! " $1}'
popd
