from typing import Union
from copy import deepcopy
from clingo.ast import *
from clingo.symbol import *
import re
from enum import Enum

from .preprocess import preprocess

# Markers for unproved goals
class UnprovedGoalState(Enum):
    NOT_EXIST = 0
    UNPROVED_YET = 1
    BACKTRACK = 2

def unproved_goal_state_to_str(failure):
    if failure == UnprovedGoalState.NOT_EXIST:
        return "NOT_EXIST"
    if failure == UnprovedGoalState.UNPROVED_YET:
        return "UNPROVED_YET"
    if failure == UnprovedGoalState.BACKTRACK:
        return "BACKTRACK"
    else:
        raise ValueError("Wrong failed-goal-marker")

def convert_numeric_string_to_number(input_string):
    if input_string.isnumeric():
        return float(input_string)

    pattern = r'([-+]?(\d+)(\.\d+)?)$'
    match = re.match(pattern, input_string)
    
    # Convert to number
    if match:
        num_str = match.group()
        return float(num_str)
    else:
        return input_string


def evaluate_num(ast: AST):
    result = _evaluate_num(ast)
    if result is not None:
        return SymbolicTerm(ast.location, String(str(result))) # simple numeric value to string.
    return ast

def _evaluate_num(ast: AST):
    # Evaluate ast into number (SymbolicTerm) if applicable.
    if ast.ast_type == ASTType.Variable:
        return None
    elif ast.ast_type == ASTType.SymbolicTerm:
        if ast.symbol.type == SymbolType.Number:
            return ast.symbol.number
        elif ast.symbol.type == SymbolType.String:
            value = convert_numeric_string_to_number(ast.symbol.string)
            if isinstance(value, float) or isinstance(value, int):
                return value
            else:
                return None
        else:
            return None
    elif ast.ast_type == ASTType.Function:
        # Predefined functions
        if ast.name == "round" and len(ast.arguments) == 1:
            # round() function
            value = _evaluate_num(ast.arguments[0])
            if value is not None:
                return round(value)
            else:
                return None
        elif ast.name == "max" and len(ast.arguments) == 2:
            # round() function
            value1 = _evaluate_num(ast.arguments[0])
            value2 = _evaluate_num(ast.arguments[1])
            if value1 is not None and value2 is not None:
                return max(value1, value2)
            else:
                return None
        elif ast.name == "min" and len(ast.arguments) == 2:
            # round() function
            value1 = _evaluate_num(ast.arguments[0])
            value2 = _evaluate_num(ast.arguments[1])
            if value1 is not None and value2 is not None:
                return min(value1, value2)
            else:
                return None
    elif ast.ast_type == ASTType.UnaryOperation:
        if ast.operator_type == UnaryOperator.Minus:
            value = _evaluate_num(ast.argument)
            if value is not None:
                return -value
            else:
                return None
    elif ast.ast_type == ASTType.BinaryOperation:
        value1 = _evaluate_num(ast.left)
        value2 = _evaluate_num(ast.right)
        if value1 is None or value2 is None:
            return None
        if ast.operator_type == BinaryOperator.Plus:
            return value1 + value2
        elif ast.operator_type == BinaryOperator.Minus:
            return value1 - value2
        elif ast.operator_type == BinaryOperator.Multiplication:
            return value1 * value2
        elif ast.operator_type == BinaryOperator.Division:
            return value1 / value2
        elif ast.operator_type == BinaryOperator.Power:
            return value1 ** value2
        elif ast.operator_type == BinaryOperator.Modulo:
            return int(value1) % int(value2)
    return None

def get_hash_head(ast:AST):
    rule_str = str(ast)
    # Hash by head symbol (rule base..^^)
    # not a(..) :-   =>    `not a`
    # if rule_str.startswith("")
    index1 = rule_str.index(":-") if ":-" in rule_str else 1000000
    index2 = rule_str.index("(") if "(" in rule_str else 1000000
    index3 = rule_str.index(".") if "." in rule_str else 1000000
    index = min(index1, index2, index3)
    if index == 1000000:
        return rule_str
    hash_head = rule_str[:index].strip()
    return hash_head

def is_negated(ast: AST) -> bool:
    if ast.ast_type != ASTType.Literal:
        raise ValueError(f"AST {str(ast)} is not Literal; thus cannot be negated")
    return ast.sign == Sign.Negation

def is_ground(ast: AST) -> bool:
    # Only true if no variables are inside this ast.
    if ast.ast_type == ASTType.Variable:
        return False
    
    # Literals
    if "atom" in ast.child_keys:
        return is_ground(ast.atom)
    # Terms
    grounded = True
    if "arguments" in ast.child_keys:
        for arg in ast.arguments:
            grounded &= is_ground(arg)
            if not grounded: # Early termination (time cutting)
                return False
    if "left" in ast.child_keys:
        grounded &= is_ground(ast.left)
    if "right" in ast.child_keys:
        grounded &= is_ground(ast.right)
    if "argument" in ast.child_keys:
        grounded &= is_ground(ast.argument)
    if "symbol" in ast.child_keys:
        grounded &= is_ground(ast.symbol)
    if "term" in ast.child_keys:
        grounded &= is_ground(ast.term)
    if "guards" in ast.child_keys:
        for arg in ast.guards:
            grounded &= is_ground(arg.term)
    return grounded

def flip_sign(ast):
    new_ast = deepcopy(ast)
    if ast.sign == Sign.Negation:
        new_ast.sign = Sign.NoSign
    elif ast.sign == Sign.NoSign:
        new_ast.sign = Sign.Negation
    else:
        raise ValueError("Does not support DoubleNegation")
    return new_ast

def extract_const_list(term: AST, exclude_underscore:bool = True):
    # Refer to official Potassco guide for details in Transformer.
    const_list = []
    class ConstantTracker(Transformer):
        def visit_SymbolicTerm(self, node):
            try:
                name = node.symbol.name
                arity = len(node.symbol.arguments)
                if not exclude_underscore or not name.startswith("_"):
                    const_list.append((name, arity))
                self.visit_children(node)
                return node # No change
            except Exception:
                # number, etc
                return node
        def visit_Function(self, node):
            name = node.name
            arity = len(node.arguments)
            if not exclude_underscore or not name.startswith("_"):
                const_list.append((name, arity))
            self.visit_children(node)
            return node # No change
    
    # parse_string converts string to AST.
    result = []
    try:
        if term.strip().endswith('.'):
            parse_string(term, result.append)
        # else, add a period and parse
        else:
            parse_string(term + ".", result.append)
        result = result[1]  # AST
        ConstantTracker()(result)
    except Exception as e:
        return []
    return const_list

def anonymize_vars(goal: Union[str, AST]):
    PATTERN = r"([,( ])(_*[A-Z][A-Za-z_0-9]*)(?=[,)]| [+\-*/%><=!])"
    if isinstance(goal, AST):
        is_rule = (goal.ast_type == ASTType.Rule)
        goal = str(goal)
        goal = re.sub(PATTERN, "\g<1>_", goal) # Remove variables
        if is_rule:
            return parse_line(goal)
        else:
            return parse_line(goal + ".").head
    else:
        return re.sub(PATTERN, "\g<1>_", goal) # Remove variables

def parse_line(goal: str):
    # Convert all floating numbers (and integers) into string
    # Do not convert strings enclosed in double-quote.
    # FIXME Assume that there are no escaped double quotes.
    goal_list = goal.split('"') # split with double quotes
    refined_goal_list = []
    for i, snippet in enumerate(goal_list):
        if i % 2 == 0:
            # Non-string
            snippet = snippet.replace(" is ", " = ")
            refined_goal_list.append(re.sub(r"(^|[(){}:;,\s'])(-?[0-9]+(\.[0-9]+)?)\b", r'\g<1>"\g<2>"', snippet))
        else:
            # String
            refined_goal_list.append(snippet)
    goal = '"'.join(refined_goal_list)
    goal = goal.replace('""', '"')
    _temp = []
    parse_string(goal, callback=_temp.append)
    goal: AST = _temp[1]
    return goal

def parse_program(terms: list):
    success = []
    parsed_program = []
    for term in terms:
        # Parsing.
        try:
            parsed_program.extend(preprocess(parse_line(term['asp']))) # Unpack pooling and #count aggregates, negated heads to constraints, ...
        except Exception as e:
            success.append({
                'code': 10,
                'msg': "Syntax error " + str(e)
            })
            continue
        # Success code
        success.append({
            'code': 0,
            'msg': "Success"
        })
    assert len(terms) == len(success)
    return parsed_program, success

class RenameVariableState:
    def __init__(self):
        self._idx = 0
    
    def idx(self):
        temp = self._idx
        self._idx += 1
        return temp