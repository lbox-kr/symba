import json
import random
import logging
import argparse
from datetime import datetime
import sys,os
sys.path.append(os.getcwd())

from hiereason.symba._symba import generate_abductive_proof

from hiereason.utils import HiereasonContext
from hiereason.utils.config import load_config, set_logger
from hiereason.utils.eval_utils import evaluate_answer

from langchain.callbacks import get_openai_callback

NUM_PER_CASE = 20

import sys
sys.path.append(".")

def main(args):
    random.seed(41)
    config = load_config(args.dataset, args.model)
    set_logger("symba", dataset=args.dataset, model=args.model)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    startdate = datetime.now().strftime('%Y%m%d-%H:%M:%S')

    dataset = args.dataset
    
    logging.info(f"DATASET: {dataset}")

    dataset = HiereasonContext("symba", config, dataset)
    logging.info("==============================\n")
    logging.info("PROMPT:")
    for func, prompt in dataset.prompt_data.items():
        logging.info(f"- {func}\n{prompt}\n")
    results = []
    with get_openai_callback() as cb:
        for datum in dataset.test_data:
            logging.info("==============================\n")
            logging.info(f"{json.dumps(datum, indent=4, ensure_ascii=False)}\n\n")
            logging.info("- - - - - - - - - - - - - - -")
            # try:
            result, program = generate_abductive_proof(datum, dataset)
            # except KeyboardInterrupt:
            #     exit()
            # except:
            #     logging.info(f"Did the model got correct? False (due to error in solve)")
            logging.info("\n" + str(result) + "\n")
            logging.info(json.dumps(program, indent=4, ensure_ascii=False) + "\n\n")
            results.append({
                "test_data": datum,
                "program": program
            })
            correctness = datum['label'] == (result is not None) # A goal is solved
            if result is not None and datum['label'] == True and 'goal_solved' in datum:
                # If the task is to find an unknown value by reasoning,
                correctness = evaluate_answer(datum['goal_solved'], result.root.repr) # Evaluate answer, allows numeric match (5 == 5.0)
            logging.info(f"Did the model got correct? {correctness}")
            
            # Find the diff of golden and generated program
            # gold_set = set([x['statement'] for x in datum['program']])
            # model_set = set([x['statement'] for x in program])
            # logging.info("Statements in gold / not in model output:")
            # for x in gold_set.difference(model_set):
            #     logging.info(f"- {x}")
            # logging.info("Statements in model output / not in gold:")
            # for x in model_set.difference(gold_set):
            #     logging.info(f"- {x}")
        
        # result_dir = f"logs/symba_{startdate}_{args.dataset}_result.json"
        # with open(result_dir, "w", encoding="UTF-8") as file:
        #     json.dump(results, file, indent=4, ensure_ascii=False)
        # logging.info(str(cb))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset ID.")
    parser.add_argument("--model", required=True, choices=["openai", "anthropic", "ollama"])
    args = parser.parse_args()
    main(args)