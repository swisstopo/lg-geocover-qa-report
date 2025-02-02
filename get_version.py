#!/usr/bin/env python

from setuptools_scm import get_version
import os

def get_project_version(setup_py_path):
    # Change the current working directory to the directory of setup.py
    setup_dir = os.path.dirname(setup_py_path)
    os.chdir(setup_dir)
    
    # Get the version using setuptools_scm
    version = get_version()
    
    return version

if __name__ == '__main__':
    setup_py_path = './setup.py'  # Adjust the path to your setup.py file
    version = get_project_version(setup_py_path)
    print(version)
