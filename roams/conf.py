import os

REPO_DIR = os.path.abspath(os.path.join(os.path.abspath(__file__),os.pardir,os.pardir))

TEST_DIR = os.path.join(REPO_DIR,"ROAMS","tests")

# Logging formatting
LOG_FMT = '[%(asctime)s: %(name)s: %(funcName)s] %(levelname)s: %(message)s'
TIME_LOG_FMT = "%d-%b-%y %H:%M:%S"