import json
import logging
from typing import List, Dict, Any
import re

from .validate_statements import validate_statement_list

# Top-down solver
from pysolver import get_proof_tree
from pysolver.utils import anonymize_vars, UnprovedGoalState, parse_line
from pysolver.solve import solve, ProofContext
from pysolver.unify import equivalent
from ..utils import HiereasonContext
from ..utils.chat_model import chat_model, run_prompt
from ..utils.nl_baseline_formatting import convert_body_text_for_symba

def abduction_factory(proof_context: ProofContext, body_text: str, reasoning_context: HiereasonContext, ablation_mode=None):
    visited = []

    def abduction(state, unproved_reason: UnprovedGoalState):
        """_summary_

        Args:
            doc (Dict[str, Any]): Dict with key `body_text` and `conclusion`. `conclusion` is a list of dict with keys `law_id` and `verdict`.
        """
        if unproved_reason == UnprovedGoalState.BACKTRACK:
            return False # Do not consider backtracking that might override rules
        llm=chat_model(reasoning_context.config)
        prompts = reasoning_context.prompt_data

        facts, rules = convert_body_text_for_symba(body_text, reasoning_context.dataset)

        # Reformulate goal
        curr_goal = state.goal
        curr_goal_str = anonymize_vars(str(curr_goal)) # Remove variables
        
        # Check visited to prevent infinite recursion
        for visited_goal in visited:
            if equivalent(curr_goal, visited_goal):
                return False # do not proceed
        visited.append(curr_goal)
        
        data = {"facts": facts, "rules": rules, "query": curr_goal_str}
        logging.info(f"[SOLVE] {curr_goal_str}")

        # List that stores all facts and results
        results = []

        # 1. Fact
        if ablation_mode == "-Search":
            raw_selected_facts = run_prompt(prompts['fact_translation-Search'], data, llm).split("\n")
            # raw_selected_facts = re.split(r"([^\.]+\.)\s", run_prompt(prompts['fact_translation-Search'], data, llm))
            selected_facts = []
            for f in raw_selected_facts:
                if f.strip() == "":
                    break
                results.append({"statement": f.replace("Statement: ", ""), "description": "", "is_fact": True})
        else:
            # 1-1. Selection
            raw_selected_facts = run_prompt(prompts['fact_search'], data, llm).split("\n")
            # raw_selected_facts = re.split(r"([^\.]+\.)\s", run_prompt(prompts['fact_search'], data, llm))
            selected_facts = []
            for f in raw_selected_facts:
                if f.strip() == "":
                    continue
                selected_facts.append({"description": f.replace("`", "")})
            # 1-2. Translation
            for selected_fact in selected_facts:
                if "No applicable fact" in selected_fact["description"] or "not directly given" in selected_fact['description']:
                    continue
                new_data = data.copy()
                new_data['fact'] = selected_fact["description"]
                fact_translations = re.split(r"([^\.]+\.)\s", run_prompt(prompts['fact_translation'], new_data, llm))
                fact_translations = [{"statement": x.replace("Statement: ", ""), "description": new_data['fact'], "is_fact": True} for x in fact_translations if x.strip()]
                results.extend(fact_translations)
        
        # 2. Rule
        if ablation_mode == "-Search":
            raw_selected_rules = re.split(r"([^\.]+\.)\s", run_prompt(prompts['rule_translation-Search'], data, llm))
            selected_rules = []
            for f in raw_selected_rules:
                if f.strip() == "":
                    break
                results.append({"statement": f.replace("Statement: ", ""), "description": "", "is_fact": False})
        else:
            # 2-1. Selection
            raw_selected_rules = run_prompt(prompts['rule_search'], data, llm).split("\n")
            # raw_selected_rules = re.split(r"([^\.]+\.)\s", run_prompt(prompts['rule_translation-Search'], data, llm))
            selected_rules = []
            for f in raw_selected_rules:
                if f.strip() == "":
                    continue
                selected_rules.append({"description": f})
            # 2-2. Translation
            for selected_rule in selected_rules:
                if "No applicable rule" in selected_rule["description"]:
                    continue
                new_data = data.copy()
                new_data['rule'] = selected_rule["description"]
                rule_translations = run_prompt(prompts['rule_translation'], new_data, llm).split("\n")
                # rule_translations = re.split(r"([^\.]+\.)\s", run_prompt(prompts['rule_translation'], new_data, llm))
                rule_translations = [{"statement": x.replace("Statement: ", ""), "description": new_data['rule'], "is_fact": False} for x in rule_translations if x.strip()]
                results.extend(rule_translations)
        logging.info(str(results))
        
        # 3. Symbolic validation
        valid_new_stmts, error = validate_statement_list(results, curr_goal, reasoning_context)
        for r, e in zip(results, error):
            if e != "Success":
                logging.info(f"LLM failed to generate valid code: {str(r['statement'])} => {e}")
                if ablation_mode == "-Unify" and "Syntax error" not in e:
                    # Ablation: accept non-unifying statements
                    valid_new_stmts.append(r)
        
        is_any_fact_or_rule_proved = False
        is_any_fact_proved = False
        for stmt in valid_new_stmts:
            # If a fact is proved, do not observe rules.
            if is_any_fact_proved and not stmt['is_fact']:
                continue

            # # 4. Self validation - optional
            # if ablation_mode == "-SelfVal" or ablation_mode == "-Val":
            #     pass
            # else:
            #     # Reformulate description
            #     stmt["description_raw"] = stmt["description"]
            #     new_data = data.copy()
            #     new_data['statement'] = stmt["statement"]
            #     stmt["description"] = run_prompt(prompts['statement_to_text_translation'], new_data, llm)
            #     # Perform self validation
            #     new_data = data.copy()
            #     new_data['description'] = stmt["description"]
            #     self_validation_result = run_prompt(prompts['validate_description'], new_data, llm)
            #     self_validation_result = "yes" in self_validation_result.lower()
            #     if not self_validation_result:
            #         continue
            # Reach here -> stmt is considered valid
            logging.info(f"`{stmt['statement']}` Accepted")

            # Update the symbolic database
            proof_context.add_rule(stmt)
            # remove cached proof because new rule has been added
            if curr_goal_str in proof_context.proof_dict:
                proof_context.proof_dict.pop(curr_goal_str)
            # Send signal to solver that new rule has been added
            is_any_fact_or_rule_proved = True
            is_any_fact_proved = is_any_fact_proved or stmt['is_fact']
        
        return is_any_fact_or_rule_proved # If return True, the solver will reattempt to prove the goal.

    return abduction

def generate_abductive_proof(doc: Dict[str, Any], reasoning_context: HiereasonContext, ablation_mode=None):
    """_summary_

    Args:
        doc (Dict[str, Any]): Dict with key `body_text` and `conclusion`. `conclusion` is a list of dict with keys `law_id` and `verdict`.
    """

    body_text = doc.get("body_text")
    result_trees = []

    # Parse goal
    goal = parse_line(doc["goal"] + ".").head
    # Loop through goals to prove
    logging.info(f"?- {goal}.")

    # Create initial program with pre-defined rules
    program = []
    for wd in reasoning_context.world_data:
        if wd['name'] in doc['world_model']:
            program.extend(wd['statements'])
    initial_program = [p['statement'] for p in program]
    proof_context = ProofContext()
    for line in program:
        line['asp'] = line['statement'] # FIXME temporary fix for legacy compatibility
        proof_context.add_rule(line)

    # Run solve with failure callback
    try:
        proofs = solve(
            goal,
            proof_context,
             # Ablation mode in ['-Search', '-Symval', '-SelfVal', '-Val']
            unproved_callback=abduction_factory(proof_context, body_text, reasoning_context, ablation_mode=ablation_mode)
        )
    except RecursionError:
        logging.info("Proof cannot be completed due to infinite recursion, mainly due to the solver capacity.")
        return None, []

    # Analyze results
    program = proof_context.program
    program = [p for p in program if p['statement'] not in initial_program]
    logging.info(f"------------------")
    logging.info(f"{len(proofs)} proofs found")
    if len(proofs) == 0:
        return None, program
    if len(proofs) < 30:
        # Generate proof tree
        proof = get_proof_tree(proof_context.program, goal)
        result_tree = proof
    else:
        result_tree = str(proofs[0])
    return result_tree, program