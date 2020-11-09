from pyats.easypy import run
import containers


def main():
    # run api launches a testscript as an individual task.
    run('connectivity_checks.py')
