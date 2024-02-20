from typing import List

from clingo.ast import AST, ASTType

from pysolver.unify import find_bindings
from pysolver.utils import parse_line, extract_const_list


def validate_statement_list(statement_list: List, goal: AST, reasoning_context):
    result = []
    error = []
    for statement in statement_list:
        if not isinstance(statement, dict) or "statement" not in statement or "description" not in statement:
            error.append("Wrong dict key")
            continue
        rule: str = statement["statement"].strip()
        
        # Heuristic. Check if rule code ends with a period
        if not rule.endswith("."):
            rule += "."
        # # Heuristic. Change single to double quote
        # rule = rule.replace("'", '"')
        statement['statement'] = rule
        
        # Heuristic. Check if rule is a rule, and head is a single literal
        try:
            parsed_rule = parse_line(rule)
        except:
            error.append("Syntax error")
            continue
        if parsed_rule.ast_type != ASTType.Rule:
            error.append("Syntax error: not rule")
            continue
        if parsed_rule.head.ast_type != ASTType.Literal:
            error.append("Syntax error: head should be a plain literal")
            continue

        # Heuristic. Goal should unify with the goal to prove.
        if find_bindings(goal, parsed_rule.unpool()[0].head) is None:
            error.append(f"The statement head should start with `{goal}`.")
            continue

        # If all satisfied, add to successful results.
        statement["statement"] = rule
        result.append(statement)
        error.append("Success")
    return result, error