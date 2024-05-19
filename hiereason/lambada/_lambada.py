import json
import logging
from typing import List, Dict, Any
import re

from langchain import LLMChain
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
    goal = doc.get("goal") # is(who, how)
    # print(goal)
    goalstr = convert_goal(goal, context.dataset)

    def solve(rootnode: JustificationTreeNode, depth, implication_cache=None):
        question = rootnode.repr
        # Negation
        negation = False
        if "not" in question.lower():
            negation = True
        if depth > 5:
            return False

        logging.info(f"[SOLVE] {question}")
        # Initial setting
        prompt_facts = []
        for i in range(len(facts)):
            prompt_facts.append(f"Fact{i+1}. {facts[i]}")
        prompt_facts = " ".join(prompt_facts)
        prompt_rules = []
        for i in range(len(rules)):
            prompt_rules.append(f"Rule{i+1}. {rules[i]}")
        prompt_rules = " ".join(prompt_rules)
        data = {"facts": prompt_facts, "rules": prompt_rules, "question": question}

        # 1. Fact check
        # 1-1. Selection
        selected_fact_raw = run_prompt(prompts['factcheck_selection'], data, llm)
        try:
            # selected_fact_id = int(re.search("the most relevant fact is Fact([0-9]+)", selected_fact_raw).group(1)) - 1
            selected_fact_id = int(re.search("Fact([0-9]+)", selected_fact_raw).group(1)) - 1
            selected_fact = facts[selected_fact_id]
            logging.info(f"Fact check - found fact {selected_fact}")
        except:
            # No facts
            logging.info("Fact check - selection has failed: " + selected_fact_raw)
            selected_fact = None
            pass
        # 1-2. Verification
        if selected_fact is not None:
            new_data = data.copy()
            new_data['fact'] = selected_fact
            fact_verification_raw = run_prompt(prompts['factcheck_verification'], new_data, llm)
            logging.info("fact_verification_raw: " + fact_verification_raw)
            fact_verification= re.search("so the answer is \"yes\"",fact_verification_raw) is not None
            if re.search("so the answer is \"yes\"",fact_verification_raw):
                logging.info("Fact check - verification has suceeded")
                return True
            elif re.search("so the answer is \"no\"",fact_verification_raw):
                logging.info("Fact check - verification has failed")
                return False
            else:
                # No facts
                logging.info("Fact check - neither succeeded")
                selected_fact = None
                pass
        
        # 2. Rule selection
        # 2-1. Implication
        if implication_cache is None:
            rule_implication_raw = run_prompt(prompts['rule_implication'], data, llm)
        else:
            rule_implication_raw = implication_cache
        logging.info(rule_implication_raw)
        # 1-2. Application
        new_data = data.copy()
        new_data['rule_implications'] = rule_implication_raw
        rule_application_raw = run_prompt(prompts['rule_application'], new_data, llm)
        logging.info(rule_application_raw)
        # 1-2-1. Question implication
        # question_implication = re.search("The question is about ([^:]+):").group(1)
        rule_implications = {}
        for rule_idx, rule_impl in re.findall(r"Rule([0-9]+) (\([^,.]*?\)) is applicable to", rule_application_raw):
            rule_idx = int(rule_idx)
            rule_implications[rule_idx-1] = rule_impl
            logging.info(f"Rule Selection - Found rule : Rule{rule_idx} / {rules[rule_idx-1]}")
        if len(rule_implications) == 0:
            return negation # Negation as failure

        # 3. Goal decomposition
        goal_decompositions = []
        for rule_id, rule_impl in rule_implications.items():
            # For each rules,
            new_data = data.copy()
            new_data["rule"] = rules[rule_id]
            goal_decomposition_raw = run_prompt(prompts['goal_decomposition'], new_data, llm)
            # print(goal_decomposition_raw)
            try:
                goal_decomposition = re.search(r"so the question breaks down to (.*)$", goal_decomposition_raw).group(1)
                goal_decomposition = goal_decomposition.split(",")
                goal_decomposition = [x.strip().capitalize() for x in goal_decomposition]
                goal_decompositions.append((rule_id, goal_decomposition))
                log_goal_decomposition_str = " / ".join(goal_decomposition)
                logging.info(f"Goal decomposition - {rules[rule_id]} decomposes into : {log_goal_decomposition_str}")
            except:
                logging.info(f"Goal decomposition failure")
                return negation # Negation as failure
                continue
        
        # Rerank() -> ascending sort by # of subgoals
        sorted(goal_decompositions, key=lambda x: len(x[1]))
        rule_satisfied = False
        for rule_id, goal_decomposition in goal_decompositions:
            # Prove subgoals
            is_all_subgoals_proved = True
            logging.info(f"Goal decomposition - Enter subgoals for {question}")
            for subgoal in goal_decomposition:
                new_node = JustificationTreeNode(subgoal)
                rootnode.add_child(new_node)
                if solve(new_node, depth+1, implication_cache=implication_cache):
                    pass
                else:
                    new_node.repr = "FAILED - " + new_node.repr
                    is_all_subgoals_proved = False
                    break
            if is_all_subgoals_proved:
                rule_satisfied = True
                logging.info(f"Goal decomposition - Exit subgoals for {question}")
                logging.info(f"Prove Subgoals - All subgoals proved for {question}")
                # 4. Sign agreement
                sign_agreement_raw = run_prompt(prompts['sign_agreement'], new_data, llm)
                print(sign_agreement_raw)
                if "so signs agree" in sign_agreement_raw:
                    logging.info(f"Sign agreement - Signs agree for {question} & {rules[rule_id]}")
                    # Subgoals all proved & Signs agree
                    return True
                else:
                    logging.info(f"Sign agreement - Signs do NOT agree for {question} & {rules[rule_id]}")
        if not rule_satisfied:
            # If no rules and facts are applicable,
            return negation
        else:
            return False

    rootnode = JustificationTreeNode(goalstr)
    result = solve(rootnode, 0)
    if not result:
        rootnode.repr = "FAILED - " + rootnode.repr
    logging.info(result)
    return result, rootnode._pprint([False], -1)