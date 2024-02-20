from typing import Dict
from copy import deepcopy
from functools import lru_cache

from clingo.ast import *
from clingo.symbol import *

from .utils import evaluate_num

def find_bindings(ast1: AST, ast2: AST):
    # Entry for _unify, actual recursive function
    # perform initial deepcopy
    ast1 = deepcopy(ast1)
    ast2 = deepcopy(ast2)
    return _find_bindings(ast1, ast2)

@lru_cache(maxsize=1024) # optimization
def _find_bindings(ast1: AST, ast2: AST):
    # Variable
    if ast1.ast_type == ast2.ast_type == ASTType.Variable:
        return {ast1.name: ast2} # FIXME??
        # raise ValueError("Unification failed; two variables cannot be unified")
    elif ast1.ast_type == ASTType.Variable:
        return {ast1.name: ast2}
    elif ast2.ast_type == ASTType.Variable:
        return {ast2.name: ast1}
    
    # SymbolicAtom
    elif ast1.ast_type == ast2.ast_type == ASTType.SymbolicAtom:
        return _find_bindings(ast1.symbol, ast2.symbol)

    # SymbolicTerm
    elif ast1.ast_type == ast2.ast_type == ASTType.SymbolicTerm:
        if ast1.symbol.type == SymbolType.String and ast2.symbol.type == SymbolType.String:
            # Check for numbers to assign "5" == "5.0"
            if evaluate_num(ast1) == evaluate_num(ast2):
                return {}
            else:
                return None
        else:
            if ast1.symbol == ast2.symbol:
                return {}
            else:
                return None

    # UnaryOperation
    elif ast1.ast_type == ast2.ast_type == ASTType.UnaryOperation:
        if ast1.operator_type == ast2.operator_type:
            bindings = _find_bindings(ast1.argument, ast2.argument)
            return bindings
        else:
            return None
    
    # BinaryOperation
    elif ast1.ast_type == ast2.ast_type == ASTType.BinaryOperation:
        # Deepcopy because substitution is required for correct behavior
        ast1 = deepcopy(ast1); ast2 = deepcopy(ast2)
        if ast1.operator_type == ast2.operator_type:
            bindings = _find_bindings(ast1.left, ast2.left)
            if bindings is None:
                return None
            bind(ast1, bindings)
            bind(ast2, bindings)
            bindings.update(_find_bindings(ast1.right, ast2.right))
            return bindings
        else:
            return None
    
    # Function
    elif ast1.ast_type == ast2.ast_type == ASTType.Function:
        # Deepcopy because substitution is required for correct behavior
        ast1 = deepcopy(ast1); ast2 = deepcopy(ast2)
        if ast1.name == ast2.name and len(ast1.arguments) == len(ast2.arguments):
            bindings = {}
            for i in range(len(ast1.arguments)):
                arg1 = ast1.arguments[i]
                arg2 = ast2.arguments[i]
                args_binding = _find_bindings(arg1, arg2)
                if args_binding is None:
                    # one of args do not unify
                    return None
                bind(ast1, dict(args_binding))
                bind(ast2, dict(args_binding))
                bindings.update(args_binding)
            return bindings
        else:
            return None
    
    
    # Literal
    elif ast1.ast_type == ast2.ast_type == ASTType.Literal:
        if ast1.sign == ast2.sign and ast1.atom.ast_type == ast2.atom.ast_type:
            return _find_bindings(ast1.atom, ast2.atom)
    # Boolean constant
    elif ast1.ast_type == ast2.ast_type == ASTType.BooleanConstant:
        if ast1.value == ast2.value:
            return {}
        else:
            return None
    elif ast1.ast_type == ast2.ast_type == ASTType.Comparison:
        return {} # FIXME

    return None

def equivalent(ast1, ast2):
    bindings = find_bindings(ast1, ast2)
    if bindings is None:
        return False
    for b in bindings.values():
        if b.ast_type != ASTType.Variable:
            return False
    return True

def bind(input_ast, bindings: Dict[str, AST]):
    # Explicit call stack maintaining for a bit of speedup
    if len(bindings) == 0:
        return input_ast
    stack = [input_ast]

    while len(stack) > 0:
        ast = stack.pop()
        child_keys = set(ast.child_keys)
        if "head" in child_keys:
            stack.append(ast.head)
        if "body" in child_keys:
            stack.extend(ast.body)
        if "atom" in child_keys:
            stack.append(ast.atom)
        if "arguments" in child_keys:
            for i, arg in enumerate(ast.arguments):
                if arg.ast_type == ASTType.Variable and arg.name in bindings:
                    ast.arguments[i] = bindings[arg.name]
                else:
                    stack.append(arg)
        if "left" in child_keys:
            if ast.left.ast_type == ASTType.Variable and ast.left.name in bindings:
                ast.left = bindings[ast.left.name]
            else:
                stack.append(ast.left)
        if "right" in child_keys:
            if ast.right.ast_type == ASTType.Variable and ast.right.name in bindings:
                ast.right = bindings[ast.right.name]
            else:
                stack.append(ast.right)
        if "argument" in child_keys:
            if ast.argument.ast_type == ASTType.Variable and ast.argument.name in bindings:
                ast.argument = bindings[ast.argument.name]
            else:
                stack.append(ast.argument)
        if "symbol" in child_keys:
            if ast.symbol.ast_type == ASTType.Variable and ast.symbol.name in bindings:
                ast.symbol = bindings[ast.symbol.name]
            else:
                stack.append(ast.symbol)
        if "term" in child_keys:
            if ast.term.ast_type == ASTType.Variable and ast.term.name in bindings:
                ast.term = bindings[ast.term.name]
            else:
                stack.append(ast.term)
        if "guards" in child_keys:
            for i, arg in enumerate(ast.guards):
                arg = arg.term
                if arg.ast_type == ASTType.Variable and arg.name in bindings:
                    ast.guards[i].term = bindings[arg.name]
                else:
                    stack.append(arg)