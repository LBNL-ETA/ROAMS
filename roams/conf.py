import os

REPO_DIR = os.path.abspath(os.path.join(os.path.abspath(__file__),os.pardir,os.pardir))

TEST_DIR = os.path.join(REPO_DIR,"ROAMS","tests")

# # A folder to hold results from all runs
RESULT_DIR = os.path.join(REPO_DIR,"run_results")
if not os.path.exists(RESULT_DIR):
    os.mkdir(RESULT_DIR)

import logging
import logging.config
logging.config.fileConfig(os.path.join(REPO_DIR,"logging.conf"))