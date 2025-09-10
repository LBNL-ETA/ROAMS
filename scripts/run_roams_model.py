import logging

from roams.model import ROAMSModel

if __name__=="__main__":
    log = logging.getLogger("run_roams_model")
    log.setLevel(logging.INFO)

    from argparse import ArgumentParser
    parser = ArgumentParser(
        description = "Script to run the ROAMS model with a given input file."
    )

    parser.add_argument("input_file",type=str,help="Path to the JSON input file to the ROAMS Model.")
    parser.add_argument("--debug",action="store_true",default=False,help="Whether to log debug messages to the console (they are always logged to a log file). Otherwise will log at info level.")

    args = parser.parse_args()
    loglevel = logging.DEBUG if args.debug else logging.INFO
    file = args.input_file

    log.info("Starting run")

    r = ROAMSModel(file)

    r.perform_analysis()
    
    log.info("Run finished")