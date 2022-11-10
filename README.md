# biotech

## Overview

`main.bash` -- contains pipeline implemented as bash script

`./toil-hello-worlds` -- contains useful toil examples

`toil-pipeline.py` -- pipeline implemented with toil

## Usage

Downloads resources:
 - https://www.ncbi.nlm.nih.gov/sra/SRX18175272 as sequence.fastq.gz
 - https://www.ncbi.nlm.nih.gov/assembly/GCF_000005845.2/ as reference.fna

It is expected that you have bwa, fastqc, samtools on your PATH
For toil pipeline it is expected that input folder contains `reference.fna` and `sequence.fastq.gz`

`python toil-pipeline.py file:my-job-store --logFile="./log.txt"`

`main.bash reference.fna.gz sequence.fastq.gz`
