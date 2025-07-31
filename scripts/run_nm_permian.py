import logging

from roams.model import ROAMSModel

if __name__=="__main__":
    log = logging.getLogger("run_nm_permian")
    log.setLevel(logging.INFO)

    from argparse import ArgumentParser
    parser = ArgumentParser(
        description = "Script to run the ROAMS model for the New Mexico Permian campaign"
    )

    parser.add_argument("--debug",action="store_true",default=False,help="Whether to log debug messages to the console (they are always logged to a log file)")

    args = parser.parse_args()
    loglevel = logging.DEBUG if args.debug else logging.INFO

    log.info("Starting run")

    r = ROAMSModel("/Users/eneill/repos/ROAMS/input files/nm_perminan_json_input.json")

    r.perform_analysis()
    
    log.info("Run finished")