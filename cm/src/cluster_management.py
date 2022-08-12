import copy
import pickle
import re
import os
import time
import subprocess
import datetime
import itertools
import hashlib
import glob
import numpy as np


class cluster_management(object):
    def __init__(self):
        return

    @staticmethod
    def get_server_and_user():
        server = subprocess.check_output(
            ['uname', '-n']).decode("utf-8").strip()
        user = subprocess.check_output('echo $HOME', shell=True).decode(
            "utf-8").strip().split('/')[-1]
        return server, user

    @staticmethod
    def get_sge_file_content(command_list, gpu, max_time,
                             node=-1,          # UIUC ALF cluster only
                             num_nodes=None,    # blue waters/RCC
                             use_aprun=True,   # blue waters only
                             ppn=12,
                             partition='amdsmall',
                             exclusive=False   # RCC only
                             ):
        assert (isinstance(command_list, list))
        temp_commands = []
        for item in command_list:
            item = item.strip()
            if item[-1] != '&':
                item += ' &'         # to run multiple jobs in a script
            temp_commands.append(item)
        assert (len(temp_commands) == len(command_list))
        server_name, _ = cluster_management.get_server_and_user()

        if num_nodes is None:
            num_nodes = len(command_list)
        s = partition[:4] if partition == "a100-4" else partition
        gpu_option_string = f'#SBATCH --gres=gpu:{s}:1' if gpu else ''
        node_string = "" if node == -1 else "#$ -l hostname=compute-0-%d" % node
        exclusive_mode_string = '#SBATCH --exclusive' if exclusive else ''

        content_for_sge_file = '''#!/bin/bash
#SBATCH --partition={}
#SBATCH --time={}
#SBATCH --nodes={}
#SBATCH --mem=10G
{}
{}
export OPENMM_PLUGIN_DIR='/home/sarupria/lee04088/.conda/envs/autoencoder/lib/plugins'
set -e
module purge
module load cuda/11.2

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/panfs/roc/msisoft/anaconda/python3-2020.07-mamba/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/panfs/roc/msisoft/anaconda/python3-2020.07-mamba/etc/profile.d/conda.sh" ]; then
        . "/panfs/roc/msisoft/anaconda/python3-2020.07-mamba/etc/profile.d/conda.sh"
    else
        export PATH="/panfs/roc/msisoft/anaconda/python3-2020.07-mamba/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<
conda activate /home/sarupria/lee04088/.conda/envs/autoencoder
export PATH="/home/sarupria/dpert/.local/bin:${{PATH}}"
export PYTHONPATH="/home/sarupria/dpert/plumed_helper:${{PYTHONPATH}}"
export PYTHONPATH="/home/sarupria/dpert/cluster_management/cm/src:${{PYTHONPATH}}"

cd $SLURM_SUBMIT_DIR
{}
wait       # to wait for all jobs to finish
echo "This job is DONE!"
exit 0
'''.format(partition, max_time, num_nodes, gpu_option_string, exclusive_mode_string, '\n'.join(temp_commands))
        return content_for_sge_file

    @staticmethod
    def generate_sge_filename_for_a_command(command):
        sge_filename = command.split('>')[0]
        for item in ('"', '&', 'python', "'", '\\'):
            sge_filename = sge_filename.replace(item, '')
        for item in (' ', '..', '/', '--', ':'):
            sge_filename = sge_filename.replace(item, '_')
        sge_filename = sge_filename.strip() + '.sge'
        sge_filename = re.sub('_+', '_', sge_filename)
        if len(sge_filename) > 255:  # max length of file names in Linux
            temp = hashlib.md5()
            temp.update(sge_filename.encode('utf-8'))
            sge_filename = "h_" + temp.hexdigest() + sge_filename[-200:]
        return sge_filename

    @staticmethod
    def create_sge_files_from_a_file_containing_commands(
            command_file, num_jobs_per_file=1, folder_to_store_sge_files='../sge_files/', run_on_gpu=False):
        with open(command_file, 'r') as commmand_file:
            commands_to_run = commmand_file.readlines()
            commands_to_run = [x.strip() for x in commands_to_run]
            commands_to_run = [x for x in commands_to_run if x != ""]
            cluster_management.create_sge_files_for_commands(
                commands_to_run, num_jobs_per_file=num_jobs_per_file,
                folder_to_store_sge_files=folder_to_store_sge_files,
                run_on_gpu=run_on_gpu
            )

        return commands_to_run

    @staticmethod
    def create_sge_files_for_commands(list_of_commands_to_run,
                                      # may have more than 1 jobs in each file, for efficiency of scheduling
                                      partition='a100-4',
                                      num_jobs_per_file=1,
                                      folder_to_store_sge_files='../sge_files/',
                                      run_on_gpu=True, ppn=12, max_time='01:00:00'):
        if folder_to_store_sge_files[-1] != '/':
            folder_to_store_sge_files += '/'
        if not os.path.exists(folder_to_store_sge_files):
            subprocess.check_output(['mkdir', folder_to_store_sge_files])
        sge_file_list = []
        num_files = int(
            np.ceil(float(len(list_of_commands_to_run)) / float(num_jobs_per_file)))
        for index in range(num_files):
            item_command_list = list_of_commands_to_run[index *
                                                        num_jobs_per_file: (index + 1) * num_jobs_per_file]
            sge_filename = cluster_management.generate_sge_filename_for_a_command(
                item_command_list[0])  # use first command to generate file name
            sge_filename = folder_to_store_sge_files + sge_filename
            sge_file_list.append(sge_filename)

            content_for_sge_files = cluster_management.get_sge_file_content(
                item_command_list, gpu=run_on_gpu, partition=partition, max_time=max_time, ppn=ppn)
            with open(sge_filename, 'w') as f_out:
                f_out.write(content_for_sge_files)
                f_out.write("\n")
        assert (len(sge_file_list) == num_files)
        return sge_file_list

    @staticmethod
    def get_num_of_running_jobs():
        _, user = cluster_management.get_server_and_user()
        output = subprocess.check_output(['qstat', '-u', user]).decode("utf-8")
        all_entries = output.strip().split('\n')[2:]   # remove header
        # remove unrelated lines
        all_entries = [item for item in all_entries if user in item]
        all_entries = [item for item in all_entries if (
            not item.strip().split()[4] == 'dr')]   # remove job in "dr" state
        num_of_running_jobs = len(all_entries)
        # print('checking number of running jobs = %d\n' % num_of_running_jobs)
        return num_of_running_jobs

    @staticmethod
    def submit_sge_jobs_and_archive_files(job_file_lists,
                                          num  # num is the max number of jobs submitted each time
                                          ):
        dir_to_archive_files = '../sge_files/archive/'

        if not os.path.exists(dir_to_archive_files):
            os.makedirs(dir_to_archive_files)

        assert(os.path.exists(dir_to_archive_files))
        sge_job_id_list = []
        for item in job_file_lists[0:num]:
            output_info = subprocess.check_output(
                ['sbatch', item]).decode("utf-8").strip()
            sge_job_id_list.append(
                cluster_management.get_job_id_from_qsub_output(output_info))
            print('submitting ' + str(item))
            subprocess.check_output(
                ['mv', item, dir_to_archive_files])  # archive files
        return sge_job_id_list

    @staticmethod
    def get_job_id_from_qsub_output(output_info):
        return output_info.split()[-1]

    @staticmethod
    def submit_a_single_job_and_wait_until_it_finishes(job_sge_file):
        job_id = cluster_management.submit_sge_jobs_and_archive_files(
            [job_sge_file], num=1)[0]
        print("job = %s, job_id = %s" % (job_sge_file, job_id))
        while cluster_management.is_job_on_cluster(job_id):
            time.sleep(10)
        print("job (id = %s) done!" % job_id)
        return job_id

    @staticmethod
    def run_a_command_and_wait_on_cluster(command, partition='k40', ppn=24, gpu=True):
        print('running %s on cluster' % command)
        sge_file = cluster_management.create_sge_files_for_commands([command], partition=partition, ppn=ppn, run_on_gpu=gpu)[
            0]
        jobid = cluster_management.submit_a_single_job_and_wait_until_it_finishes(
            sge_file)
        return jobid

    @staticmethod
    def get_output_and_err_with_job_id(job_id):
        out_file = 'slurm-{}.out'.format(job_id)
        err_file = 'slurm-{}.err'.format(job_id)
        assert(os.path.exists(out_file))
        # assert(os.path.exists(err_file))
        # temp_file_list = subprocess.check_output(
        #    ['ls']).decode("utf-8").strip().split('\n')
        # out_file = list(
        #    [x for x in temp_file_list if '.sge.o' + job_id in x])[0]
        # err_file = list(
        #    [x for x in temp_file_list if '.sge.e' + job_id in x])[0]
        return out_file, err_file

    @staticmethod
    def get_sge_files_list():
        result = [x for x in subprocess.check_output(
            ['ls', '../sge_files']).decode("utf-8").split('\n') if x[-3:] == "sge"]
        result = ['../sge_files/' + x for x in result]
        return result

    @staticmethod
    def submit_new_jobs_if_there_are_too_few_jobs(num):
        if cluster_management.get_num_of_running_jobs() < num:
            job_list = cluster_management.get_sge_files_list()
            job_id_list = cluster_management.submit_sge_jobs_and_archive_files(job_list,
                                                                               num - cluster_management.get_num_of_running_jobs())
        else:
            job_id_list = []
        return job_id_list

    @staticmethod
    def monitor_status_and_submit_periodically(num,
                                               num_of_running_jobs_when_allowed_to_stop=0,
                                               # monitor_mode determines whether it can go out of first while loop
                                               monitor_mode='normal',
                                               check_error_for_submitted_jobs=True):
        if monitor_mode == 'normal':
            min_num_of_unsubmitted_jobs = 0
        elif monitor_mode == 'always_wait_for_submit':
            min_num_of_unsubmitted_jobs = -1
        else:
            raise Exception('monitor_mode not defined')

        submitted_job_id = []
        num_of_unsubmitted_jobs = len(cluster_management.get_sge_files_list())
        # first check if there are unsubmitted jobs
        while len(submitted_job_id) > 0 or num_of_unsubmitted_jobs > min_num_of_unsubmitted_jobs:
            time.sleep(10)
            if check_error_for_submitted_jobs:
                cluster_management.get_sge_dot_e_files_in_current_folder_and_handle_jobs_not_finished_successfully()
            try:
                temp_submitted_job_id = cluster_management.submit_new_jobs_if_there_are_too_few_jobs(
                    num)
                submitted_job_id += temp_submitted_job_id
                # remove finished id of finished jobs
                submitted_job_id = list(
                    [x for x in submitted_job_id if cluster_management.is_job_on_cluster(x)])
                print("submitted_job_id = %s" % str(submitted_job_id))
                num_of_unsubmitted_jobs = len(
                    cluster_management.get_sge_files_list())
            except:
                print("not able to submit jobs!\n")

        # then check if all jobs are done (not really, since there could be multiple cluster_management running)
        while cluster_management.get_num_of_running_jobs() > num_of_running_jobs_when_allowed_to_stop:
            time.sleep(10)
        return

    @staticmethod
    # input could be sge file name or job id
    def is_job_on_cluster(job_sgefile_name):
        server, user = cluster_management.get_server_and_user()

        result = job_sgefile_name in subprocess.check_output(
            ['squeue', '-u', user]).decode("utf-8")
        return result

    @staticmethod
    def check_whether_job_finishes_successfully(job_sgefile_name, latest_version=True):
        """
        return value:
        0: finishes successfully
        3: not finished
        1: finishes with exception
        2: aborted due to time limit or other reason
        -1: job does not exist
        """
        job_finished_message = 'This job is DONE!'
        # first we check whether the job finishes
        if cluster_management.is_job_on_cluster(job_sgefile_name):
            return 3  # not finished
        else:
            all_files_in_this_dir = sorted(glob.glob('*'))
            out_file_list = [
                x for x in all_files_in_this_dir if job_sgefile_name + ".o" in x]
            err_file_list = [
                x for x in all_files_in_this_dir if job_sgefile_name + ".e" in x]

            if len(out_file_list) == 0 or len(err_file_list) == 0:
                print("%s does not exist" % job_sgefile_name)
                return -1

            if latest_version:   # check output/error information for the latest version, since a job could be submitted multiple times
                job_serial_number_list = [
                    int(x.split('.sge.o')[1]) for x in out_file_list]
                job_serial_number_of_latest_version = max(
                    job_serial_number_list)
                latest_out_file = next(filter(lambda x: str(
                    job_serial_number_of_latest_version) in x, out_file_list))
                latest_err_file = next(filter(lambda x: str(
                    job_serial_number_of_latest_version) in x, err_file_list))
                with open(latest_out_file, 'r') as out_f:
                    out_content = [item.strip() for item in out_f.readlines()]

                with open(latest_err_file, 'r') as err_f:
                    err_content = [item.strip() for item in err_f.readlines()]
                    err_content = [
                        x for x in err_content if "Traceback (most recent call last)" in x]

                if (job_finished_message in out_content) and (len(err_content) != 0):
                    print("%s ends with exception" % job_sgefile_name)
                    return 1
                elif not job_finished_message in out_content:
                    print("%s aborted due to time limit or other reason" %
                          job_sgefile_name)
                    return 2
                else:
                    print("%s finishes successfully" % job_sgefile_name)
                    return 0
            else:
                return

    @staticmethod
    def handle_jobs_not_finished_successfully_and_archive(job_sgefile_name_list, latest_version=True):
        dir_to_archive_files = '../sge_files/archive/'
        folder_to_store_sge_files = '../sge_files/'
        if not os.path.exists(dir_to_archive_files):
            subprocess.check_output(['mkdir', dir_to_archive_files])

        if not os.path.exists(folder_to_store_sge_files):
            subprocess.check_output(['mkdir', folder_to_store_sge_files])

        for item in job_sgefile_name_list:
            status_code = cluster_management.check_whether_job_finishes_successfully(
                item, latest_version)
            if status_code in (1, 2):
                if os.path.isfile(dir_to_archive_files + item):
                    print("restore sge_file: %s" % item)
                    subprocess.check_output(
                        ['cp', dir_to_archive_files + item, folder_to_store_sge_files])
                    assert (os.path.exists(folder_to_store_sge_files + item))
                else:
                    print("%s not exists in %s" % (item, dir_to_archive_files))

            if status_code in (0, 1, 2):  # archive .o/.e files for finished jobs
                print("archive .o/.e files for %s" % item)
                all_files_in_this_dir = sorted(glob.glob('*'))
                temp_dot_o_e_files_for_this_item = [
                    x for x in all_files_in_this_dir if (item + '.o' in x) or (item + '.e' in x)]
                for temp_item_o_e_file in temp_dot_o_e_files_for_this_item:
                    subprocess.check_output(
                        ['mv', temp_item_o_e_file, dir_to_archive_files])
        return

    @staticmethod
    def get_sge_dot_e_files_in_current_folder_and_handle_jobs_not_finished_successfully(latest_version=True):
        sge_e_files = glob.glob('*.sge.e*')
        sge_files = [item.split('.sge')[0] + '.sge' for item in sge_e_files]
        sge_files = list(set(sge_files))
        # print "sge_files = %s" % str(sge_files)
        cluster_management.handle_jobs_not_finished_successfully_and_archive(
            sge_files, latest_version)
        return
