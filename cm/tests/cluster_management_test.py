'''This is a test for functionality of ANN_simulation.py
'''

import sys, os, math, subprocess, matplotlib
from functools import reduce
matplotlib.use('agg')

sys.path.append('../src/')  # add the source file folder

from cluster_management import *
from numpy.testing import assert_almost_equal, assert_equal


class test_cluster_management(object):
    @staticmethod
    def test_create_sge_files_from_a_file_containing_commands():
        server_name, _ = cluster_management.get_server_and_user()
        if not server_name == 'kengyangyao-pc':
            input_file = '../tests/dependency/command_file.txt'
            folder_to_store_sge_files = '../tests/dependency/out_sge/'
            if os.path.exists(folder_to_store_sge_files):
                subprocess.check_output(['rm', '-rf', folder_to_store_sge_files])

            subprocess.check_output(['mkdir', folder_to_store_sge_files])

            temp = cluster_management()
            commands = temp.create_sge_files_from_a_file_containing_commands(input_file, 1, folder_to_store_sge_files)
            commands = [x[:-1].strip() for x in commands]
            print(commands)
            for out_file in subprocess.check_output(['ls', folder_to_store_sge_files]).strip().split('\n'):
                with open(folder_to_store_sge_files + out_file, 'r') as temp_file:
                    content = temp_file.readlines()
                    content = [x.strip() for x in content]
                    this_command = [x for x in content if x.startswith('python')]
                    print(this_command[0])
                    assert this_command[0] in commands
            subprocess.check_output(['rm', '-rf', folder_to_store_sge_files])
        return

    @staticmethod
    def test_generate_sge_filename_for_a_command():
        actual = cluster_management.generate_sge_filename_for_a_command('python main____work.py :::: && -- ../target')
        expected = '_main_work.py_target.sge'
        assert (actual == expected), (actual, expected)
        return
