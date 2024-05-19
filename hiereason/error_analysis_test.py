import json
import random
import logging
import argparse
from datetime import datetime
import sys,os
sys.path.append(os.getcwd())

from hiereason.utils import HiereasonContext
from hiereason.utils.config import load_config, set_logger
from hiereason.utils.chat_model import chat_model

from langchain.callbacks import get_openai_callback
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate

NUM_PER_CASE = 20

def run_prompt(prompt, data, llm):
    chain = LLMChain(
        llm=llm,
        prompt=ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant that completes the user query following the examples."), ("human", prompt)
        ])
    )
    result = str(chain.run(data))
    return result

def main(args):
    random.seed(41)
    config = load_config(args.dataset)
    set_logger("symba", dataset=args.dataset)
    startdate = datetime.now().strftime('%Y%m%d-%H:%M:%S')

    dataset = args.dataset
    
    logging.info(f"DATASET: {dataset}")

    dataset = HiereasonContext("symba", config, dataset)
    llm=chat_model(dataset.config)
    logging.info("==============================\n")
    logging.info("PROMPT:")
    for func, prompt in dataset.prompt_data.items():
        logging.info(f"- {func}\n{prompt}\n")
    
    # Test data
    with open("data/proofwriter_dep5/error_analysis_data.json") as file:
        test_data = json.load(file)
    
    result_table = []
    with get_openai_callback() as cb:
        idx = 0
        for _bound in [True, False]:
            for _length in range(15, 25+1):
                sum = 0
                for _ in range(30):
                    datum = test_data[idx]
                    logging.info("==============================\n")
                    logging.info(f"{json.dumps(datum, indent=4, ensure_ascii=False)}\n\n")
                    logging.info("- - - - - - - - - - - - - - -")
                    # call experiment
                    result = run_prompt(dataset.prompt_data['rule_selection'], {"rules": datum['body_text'], "query": datum['goal']}, llm)
                    logging.info("\n" + str(result) + "\n")
                    # Evaluate answer
                    correctness = (datum['rule'] in result)
                    logging.info(f"Did the model got correct? {correctness}")
                    if correctness:
                        sum += 1
                    # increment index
                    idx += 1
                # append results
                result_table.append([str(_bound), str(_length), str(round(sum/30*100, 2))])
        
        # Convert result into csv
        result_dir = f"logs/symba_{startdate}_{args.dataset}_erroranalysis_result.csv"
        with open(result_dir, "w", encoding="UTF-8") as file:
            for r in result_table:
                line = ",".join(r) # bound,length,recall(n/30)
                file.write(line + "\n")
        logging.info(str(cb))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset ID.")
    args = parser.parse_args()
    main(args)