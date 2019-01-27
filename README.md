This repository includes helper code for cluster management, including:

- generate submission scripts for different clusters/servers given command list (`get_sge_files_from_command_list_file.py`)

- monitor jobs and maintain a constant number of running jobs (`resume_submit.py`)

- monitor job end states and resubmit failed jobs (`resume_submit.py`)

- one-liner job submission command (e.g. `python auto_qsub.py "echo excited" --gpu 1 --submit`)

Most of the code is moved from https://github.com/weiHelloWorld/accelerated_sampling_with_autoencoder.
