"""
Setup script for courier-server
Requires GitPython to be installed
"""

import os, shutil, sys
from setuptools import setup, find_packages
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


# onerror is taken from pathutils.py, version 0.2.6
# Functions useful for working with files and paths.
# http://www.voidspace.org.uk/python/recipebook.shtml#utils

# Copyright Michael Foord 2004
# Released subject to the BSD License
# Please see http://www.voidspace.org.uk/python/license.shtml
def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise

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
