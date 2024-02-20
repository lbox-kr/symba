from typing import *

from .utils import parse_line, parse_program
from .solve import solve
from .proof_state import ProofContext
from .justification_tree import *
import logging

def get_proof_tree(program: List[Dict[str, Any]], goal: AST) -> JustificationTree:
    logging.debug(f"?- {str(goal)}.")

    context = ProofContext()
    for line in program:
        context.add_rule(line)

    proofs = solve(goal, context)
    # for p in proofs:
    #     print(p)

    # Parse and merge trees
    if len(proofs) > 0:
        tree = JustificationTree(proofs)
    else:
        tree = None
        # print([str(x) for x in get_unproved_goals(program, goal)])
    return tree


def get_unproved_goals(program: List[Dict[str, Any]], goal: AST) -> List[AST]:
    logging.debug(f"?- {str(goal)}.")
    result = []
    # print(preprocessed_program)

    context = ProofContext()
    for line in program:
        context.add_rule(line)

    proofs = solve(goal, context, unproved_callback=lambda x,y : result.append((x, y)))
    return result

if __name__ == "__main__":
    program = """fin(X) :- not a(X).
not fin(X) :- a(X).
a(X) :- z(X), not b(X, _).
not a(X) :- not z(X).
not a(X) :- z(X), b(X, _).
b(X, 1) :- c(X).
not b(X, 1) :- not c(X).
b(X, 2) :- d(X).
not b(X, 2) :- not d(X).
z(k)."""
    program = program.split("\n")
    program = [{"statement": x} for x in program]
    result = get_proof_tree(program, parse_line("is(harry, cold).").head)
    print(result)
    # result = get_unproved_goals(program, parse_line("not fin(_).").head, {})
    # print([(str(x[0]), unproved_goal_state_to_str(x[1])) for x in result])