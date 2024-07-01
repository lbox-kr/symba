import json
import logging
from typing import List, Dict, Any
import re

from langchain import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

from ..utils import HiereasonContext
from ..utils.chat_model import chat_model, run_prompt
from ..utils.nl_baseline_formatting import convert_goal, convert_body_text

from pysolver.justification_tree import JustificationTreeNode


def generate_abductive_proof(doc: Dict[str, Any], context: HiereasonContext):
    """_summary_

    Args:
        doc (Dict[str, Any]): Dict with key `body_text` and `conclusion`. `conclusion` is a list of dict with keys `law_id` and `verdict`.
    """
    llm=chat_model(context.config)
    prompts = context.prompt_data

    # Reformulate body
    body_text = doc.get("body_text")
    program = []
    for wd in context.world_data:
        if wd['name'] in doc['world_model']:
            program.extend(wd['statements'])
    program = [x['description'] for x in program]
    program = "\n".join(program)
    facts, rules = convert_body_text(body_text, context.dataset, world_model=program)

    # Reformulate goal
    goal = doc.get("goal_solved", None)
    if goal is None:
        goal = doc.get("goal") # is(who, how)
    # print(goal)
    goalstr = convert_goal(goal, context.dataset)

    data = {
        "body_text": body_text,
        "question": goalstr,
        "facts": facts,
        "rules": rules
    }

    questions = run_prompt(prompts["decomposition"], data, llm)
    print(questions)
    try:
        final_question = re.search("To answer \"([^\"]+)\",", questions).group(1)
        questions = questions.split("we need to know:")[1].strip()
        print(questions)
        questions = list(re.findall(r"\"([^\"]+)\"[.,]", questions))
        questions.append(final_question)
        logging.info(questions)
    except:
        # Failed to parse
        return False, None
    
    # Custom setting where newline terminates the generation
    solution_llm=chat_model(context.config, stop_on_newline=True)
    # Solution
    current_answer = ""
    for question in questions:
        current_answer += f"Q. {question}\n"
        data["current_answer"] = current_answer
        answer = run_prompt(prompts["solution"], data, solution_llm)
        current_answer += answer.strip() + "\n"
        # logging.info("Q. " + question + " A. " + answer)
        # print("---------------")
        # print(current_answer)
    logging.info("\n" + current_answer)
    if context.dataset == "gsm8k" or context.dataset == "mawps":
        current_answer += "(Answer with only a single number.) The answer is:"
    else:
        current_answer += "(Answer with `yes` or `no`.) The answer is:"
    data["current_answer"] = current_answer
    final_answer = run_prompt(prompts["solution"], data, solution_llm).replace("The answer is: ", "").strip().lower()
    logging.info("Final answer: " + final_answer)
    
    if context.dataset == "gsm8k" or context.dataset == "mawps":
        if final_answer.endswith("."):
            final_answer = final_answer[:-1]
        try:
            return float(goalstr) == float(final_answer), None
        except ValueError: # Model generates non-numeric string
            return False, None
    if not ("yes" in final_answer or "no" in final_answer):
        return None, None # Failure
    result = "yes" in final_answer
    
    return result, None