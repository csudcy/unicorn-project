import os
import sys

from setuptools import setup
from setuptools import find_packages

from unicorn import __version__

def build_data_files_array(dir, ignore_us=[]):
    subdir_list = []
    for dirpath, dirnames, filenames in os.walk(dir):
        ignore = False
        splits = dirpath.split(os.sep)
        for x in ignore_us:
            if x in splits:
                ignore = True
                break

        if not ignore and filenames:
            filepaths = [os.path.join(dirpath, filename) for filename in filenames]
            current_dir_tuple = (dirpath, filepaths)
            subdir_list.append(current_dir_tuple)

    return subdir_list

# This script builds using the repo that this file is sitting in
BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
EGG_NAME = 'unicorn'

os.chdir(BUILD_DIR)
# Setup TP
setup(
    name=EGG_NAME,
    version=__version__,
    author='Arts Alliance Media',
    packages=[os.path.join('unicorn', 'lib', x) for x in find_packages(os.path.join(BUILD_DIR, 'unicorn', 'lib'))] + find_packages(),
    data_files=build_data_files_array(os.path.join('unicorn', 'static')) + build_data_files_array(os.path.join('unicorn', 'lib')),
    entry_points={'console_scripts': ['unicorn=unicorn.run:main']}
)

# Printing the name of the egg allows Jenkins to pick it up
print EGG_NAME + '-' + __version__ + '-py' + str(sys.version_info[0]) + '.' + str(sys.version_info[1])
