from pysolver.run_proof import get_proof_tree
from pysolver.utils import parse_line, is_ground

def evaluate_answer(term1, term2):
    # FIXME: Escape quotation marks in the answer() predicate -> currently an ad-hoc solution
    # if "answer(\"" in term1:
    #     term1_inside = term1[8:-2].replace('"', r'\"') # answer("XXX") -> XXX
    #     term1 = f"answer(\"{term1_inside}\")"
    # if "answer(\"" in term2:
    #     term2_inside = term2[8:-2].replace('"', r'\"')
    #     term2 = f"answer(\"{term2_inside}\")"
    # Generate program
    try:
        if not is_ground(parse_line(term1 + ".").head) or not is_ground(parse_line(term2 + ".").head):
            return False
    except:
        return False
    program = f"correct :- {term1} = {term2}."
    try:
        result = get_proof_tree([{"statement": program}], parse_line("correct.").head) # reuse unification feature of the solver.
    except:
        # Syntax error, and more
        print(program)
        return False
    if result is not None:
        return True
    else:
        return False

def postprocess_cot(result, dataset):
    try:
        result = result.split("####")[1].strip()
        return result
    except:
        return ""