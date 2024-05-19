import json
import logging
from typing import List, Dict, Any
import re

from langchain import LLMChain
from langchain.prompts import ChatPromptTemplate

from ..utils import HiereasonContext
from ..utils.chat_model import chat_model, run_prompt
from ..utils.nl_baseline_formatting import convert_goal
from ..utils.eval_utils import postprocess_cot

from pysolver.justification_tree import JustificationTreeNode


def generate_answer(doc: Dict[str, Any], context: HiereasonContext):
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

    # Reformulate goal
    goal = doc.get("goal_solved", None)
    if goal is None:
        goal = doc.get("goal") # is(who, how)
    # print(goal)
    goalstr = convert_goal(goal, context.dataset)
    
    negation = False
    if "not" in goalstr.lower():
        negation = True

    data = {
        "body_text": body_text,
        "question": goalstr,
        "world_model": program
    }

    result = run_prompt(prompts["few_shot"], data, llm).lower()
    logging.info("\n" + result)
    result = postprocess_cot(result, context.dataset)
    if context.dataset == "gsm8k":
        try:
            return float(goalstr) == float(result), None
        except ValueError: # Model generates non-numeric string
            return False, None
    if not ("yes" in result or "no" in result):
        return None, None # Failure
    result = "yes" in result

    return result, None