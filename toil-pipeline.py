from toil.common import Toil
from toil.job import Job
import os.path
import os
import hashlib
import subprocess

def make_path_friendly_executable(x):
    return f"/usr/bin/env {x}"

SAMTOOLS = make_path_friendly_executable("samtools")
BWA = make_path_friendly_executable("bwa")
FASTQC = make_path_friendly_executable("fastqc")
FREEBAYES = make_path_friendly_executable('freebayes')
INPUT_DIR = os.path.abspath('input')
OUTPUT_DIR = os.path.abspath('output')

REFERENCE_FNAME = os.path.join(INPUT_DIR, 'reference.fna')
REFERENCE_FILE_URL = 'file://' + REFERENCE_FNAME
SEQ_FNAME = os.path.join(INPUT_DIR, 'sequence.fastq.gz')
SEQ_FILE_URL = 'file://' + SEQ_FNAME

TEST_FNAME = os.path.join(INPUT_DIR, 'test.txt')
TEST_FILE_URL = 'file://' + TEST_FNAME

RES_SAM = "res.sam"
RES_BAM = "res.bam"
RES_BAM_SORTED = "res.sorted.bam"

# required to store index. toil doesn't let save a temp directory for later use
# it is possible to save all index files, but it is not worth the effort
TMP_DIR = os.path.abspath('_tmp')
os.makedirs(TMP_DIR, exist_ok=True)


def read_global_file_saving_ext(job, file_id, ext=".fastq.gz"):
    # temp_dir = job._fileStore.getLocalTempDir()
    def h(s):
        return abs(hash(s)) % (10 ** 8)
    temp_dir = TMP_DIR
    temp_file_name = "tmp-" + str(h(file_id)) + ext
    return job._fileStore.readGlobalFile(file_id, userPath=os.path.join(temp_dir, temp_file_name), mutable=True, cache=False)

def make_fastqc_report(job: Job, seq_fid, report_out, memory="1G", cores=1, disk="1G"):
    os.makedirs(report_out, exist_ok=True)
    seq_actual_path = read_global_file_saving_ext(job, seq_fid)
    command = f'{FASTQC} -o "{report_out}" "{seq_actual_path}"'
    job.log(f"Executing {command}")
    r = subprocess.check_output(command, shell=True).decode('utf-8')
    job.log(r)
    job.log("Made fastqc report")

def make_index(job: Job, ref_fid, memory="1G", cores=1, disk="1G"):
    ref_path = read_global_file_saving_ext(job, ref_fid, ext=".fna")
    command = f'{BWA} index {ref_path}'
    job.log(f'Executing {command}')
    job.log(subprocess.check_output(command, shell=True).decode('utf-8'))

def do_mem(job, ref_fid, seq_fid):
    job.log("doing bwa mem")
    ref_path = read_global_file_saving_ext(job, ref_fid, ".fna")
    seq_path = read_global_file_saving_ext(job, seq_fid)
    command = f'{BWA} mem {ref_path} {seq_path} > "{OUTPUT_DIR}/{RES_SAM}"'
    job.log(f'Executing {command}')
    job.log(subprocess.check_output(command, shell=True).decode('utf-8'))

def make_bam(job):
    job.log("making bam from sam")
    command = f'{SAMTOOLS} view --bam "{OUTPUT_DIR}/{RES_SAM}" > "{OUTPUT_DIR}/{RES_BAM}"'
    job.log(f"Executing {command}")
    job.log(subprocess.check_output(command, shell=True).decode('utf-8'))

def make_flag_stat(job):
    job.log("Doing flagstat")
    command = f'{SAMTOOLS} flagstat "{OUTPUT_DIR}/{RES_BAM}"'
    job.log(f"Executing {command}")
    r = subprocess.check_output(command, shell=True).decode('utf-8')
    job.log(r)
    return r

def finish(job):
    job.log("END")

def sort_bam(job):
    job.log("Sorting bam")
    command = f'{SAMTOOLS} sort "{OUTPUT_DIR}/{RES_BAM}" > "{OUTPUT_DIR}/{RES_BAM_SORTED}"'
    job.log(f'Executing {command}')
    job.log(subprocess.check_output(command, shell=True).decode('utf-8'))
    
def colling(job):
    job.log("Colling")
    command = f'{FREEBAYES}'
    job.log(f'Executing {command}')
    # TODO
    # os.system()

def decision(job, input_to_parse : str):
    line = filter(lambda x: "mapped" in x, input_to_parse.splitlines())
    line = list(line)[0]
    res = float(line.split()[4][1:-1])
    job.log(f"got {res} percent. making decision")
    msg = "OK" if res > 90 else "NOT OK"
    job.log(msg)
    if msg == "OK":
        job.addChildJobFn(finish)
    else:
        sort_job = Job.wrapJobFn(sort_bam)
        colling_job = Job.wrapJobFn(colling)
        colling_job.addChildJobFn(finish)
        sort_job.addChild(colling_job)
        job.addChild(sort_job)

def prepare(job: Job):
    ref_fid = job._fileStore.import_file(REFERENCE_FILE_URL)
    seq_fid = job._fileStore.import_file(SEQ_FILE_URL)
    global TEST_ID
    TEST_ID = job._fileStore.import_file(TEST_FILE_URL)
    return (ref_fid, seq_fid)

def make_pipeline(workflow: Toil):
    # ref_fid = workflow.importFile(REFERENCE_FILE_URL)
    # seq_fid = workflow.importFile(SEQ_FILE_URL)
    fastqc_report_out = f'{OUTPUT_DIR}/fastqc-report'

    main_job = None

    prep_job = Job.wrapJobFn(prepare)
    ref_fid = prep_job.rv(0)
    seq_fid = prep_job.rv(1)
    fastqc_job = Job.wrapJobFn(make_fastqc_report, seq_fid, fastqc_report_out) # could be done in parallel
    make_index_job = Job.wrapJobFn(make_index, seq_fid)
    do_mem_job = Job.wrapJobFn(do_mem, ref_fid, seq_fid)
    make_bam_from_sam_job = Job.wrapJobFn(make_bam)
    flag_stat_job = Job.wrapJobFn(make_flag_stat)
    decision_job = Job.wrapJobFn(decision, flag_stat_job.rv())

    prep_job.addChild(fastqc_job)
    fastqc_job.addChild(make_index_job)
    make_index_job.addChild(do_mem_job)
    do_mem_job.addChild(make_bam_from_sam_job)
    make_bam_from_sam_job.addChild(flag_stat_job)
    flag_stat_job.addChild(decision_job)

    main_job = prep_job

    def save_results(j):
        j.log("Saving results")
        return
        workflow.export_file(fastqc_job.rv(), fastqc_report_out)

    # main_job.addFollowOnJobFn(save_results)

    return main_job

if __name__ == "__main__":
    parser = Job.Runner.getDefaultArgumentParser()
    options = parser.parse_args()
    options.clean = "always"
    with Toil(options) as toil:
        toil.start(make_pipeline(toil))
