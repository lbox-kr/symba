import json
import random
import logging
import argparse
from datetime import datetime
import sys,os
sys.path.append(os.getcwd())

from hiereason.standard_prompting import generate_answer

from hiereason.utils import HiereasonContext
from hiereason.utils.config import load_config, set_logger


NUM_PER_CASE = 20

def main(args):
    random.seed(41)
    config = load_config(args.dataset)
    set_logger("standard", dataset=args.dataset)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    startdate = datetime.now().strftime('%Y%m%d-%H:%M:%S')

    dataset = args.dataset
    
    logging.info(f"DATASET: {dataset}")

    dataset = HiereasonContext("standard", config, dataset)
    logging.info("==============================\n")
    logging.info("PROMPT:")
    for func, prompt in dataset.prompt_data.items():
        logging.info(f"- {func}\n{prompt}\n")
    results = []
    for datum in dataset.test_data:
        logging.info("==============================\n")
        logging.info(f"{json.dumps(datum, indent=4, ensure_ascii=False)}\n\n")
        logging.info("- - - - - - - - - - - - - - -")
        # try:
        result, tree = generate_answer(datum, dataset)
        # except KeyboardInterrupt:
        #     exit()
        # except:
        #     logging.info(f"Did the model got correct? False (due to error in solve)")
        logging.info("\n" + str(result) + "\n")
        results.append({
            "test_data": datum,
            "program": tree
        })
        correctness = datum['label'] == result # A goal is proved -> label and result is both true
        logging.info(f"Did the model got correct? {correctness}")
    
    result_dir = f"logs/standard_{startdate}_{args.dataset}_result.json"
    with open(result_dir, "w", encoding="UTF-8") as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset ID.")
    args = parser.parse_args()
    main(args)