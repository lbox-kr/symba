from typing import List
from copy import deepcopy
import itertools

from clingo.ast import SymbolicAtom
from clingo.ast import *
from clingo.control import *
from clingo.symbol import *

def powerset(iterable):
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(len(s)+1))

def unpack_count_aggregates(term: AST) -> List[AST]:
    # {a; b; c} -> a or b or c
    assert term.ast_type == ASTType.Rule
    body = term.body

    new_body = []
    new_rules = []

    for body_lit in body:
        if body_lit.ast_type == ASTType.Literal:
            body_atom = body_lit.atom
            if body_atom.ast_type in [ASTType.Aggregate, ASTType.BodyAggregate]:
                # Found aggregate
                if body_atom.ast_type == ASTType.BodyAggregate and body_atom.function != AggregateFunction.Count:
                    raise ValueError(f"Do not support Aggregate function {body_atom.function}")

                new_body.append(
                    [[(deepcopy(lit).literal)]
                        for lit in body_atom.elements]
                )
            else:
                # Non-aggregate
                new_body.append([[body_lit]])

    # Create all possible rules
    for unpacked_body in itertools.product(*new_body):
        # Flatten list
        unpacked_body = [item for sublist in unpacked_body for item in sublist]
        # Add new rules
        new_rule = Rule(
            term.location,
            term.head,
            unpacked_body
        )
        new_rules.append(new_rule)

    return new_rules

def get_dual(rule: AST) -> List[AST]:
    assert rule.ast_type == ASTType.Rule
    rule = deepcopy(rule)

    head = rule.head
    if not (head.ast_type == ASTType.Literal and head.atom.ast_type == ASTType.SymbolicAtom):
        if 'atom' not in head.child_keys:
            return [] # Do nothing
        elif head.atom.ast_type == ASTType.BooleanConstant:
            return [] # Do nothing
        raise ValueError("All rule heads must be non-conditional simple literals")
    if head.sign == Sign.Negation:
        return [] # If rule is `not a :- ...` -> do not create duals
    # head.sign = Sign.NoSign if head.sign == Sign.Negation else Sign.Negation
    head.sign = Sign.Negation

    # Flip body literal one by one as in s(CASP).
    body_cnt = len(rule.body)
    dual_rules = []
    for i in range(body_cnt):
        body_lits = []
        # append body literals
        # for j in range(i):
        #     body_lits.append(rule.body[j])
        # flip i-th body literal
        dual_body_lit = deepcopy(rule.body[i])
        dual_body_lit.sign = Sign.NoSign if dual_body_lit.sign == Sign.Negation else Sign.Negation
        body_lits.append(dual_body_lit)
        # create new rules
        dual_rules.append(Rule(
            rule.location,
            head,
            body_lits
        ))
    return dual_rules
    
def get_explicit_dual(rule:AST) -> List[AST] :
    assert rule.ast_type == ASTType.Rule
    rule = deepcopy(rule)

    head = rule.head
    if not (head.ast_type == ASTType.Literal and head.atom.ast_type == ASTType.SymbolicAtom):
        if 'atom' not in head.child_keys:
            return [] # Do nothing
        elif head.atom.ast_type == ASTType.BooleanConstant:
            return [] # Do nothing
        raise ValueError("All rule heads must be non-conditional simple literals")
    
    if head.sign == Sign.NoSign:
        original_head = deepcopy(head)
        # Flip to body as integrity constriant
        if head.atom.symbol.ast_type in [ASTType.Function, ASTType.SymbolicTerm]:
            # not a() :-
            head.atom.symbol = UnaryOperation(
                head.location,
                UnaryOperator.Minus,
                deepcopy(head)
            )
            head.sign = Sign.Negation
            return [Rule(
                rule.location,
                head,
                [original_head]
            )]
        elif head.atom.symbol.ast_type == ASTType.UnaryOperation and head.atom.symbol.operator_type == UnaryOperator.Minus:
            # not -a() :-
            # Get the (classically) negated term,
            head.atom.symbol = head.atom.symbol.argument
            if head.atom.symbol.ast_type == ASTType.Function:
                # not -a() :-
                head.sign = Sign.Negation
                return [Rule(
                    rule.location,
                    head,
                    [original_head]
                )]
            elif head.atom.symbol.ast_type == ASTType.SymbolicTerm:
                # not -a :-
                head.sign = Sign.Negation
                return [Rule(
                    rule.location,
                    head,
                    [original_head]
                )]
    return []

def get_constraints(rule:AST) -> List[AST] :
    assert rule.ast_type == ASTType.Rule
    rule = deepcopy(rule)
    constraints = []

    head = rule.head
    if not (head.ast_type == ASTType.Literal and head.atom.ast_type == ASTType.SymbolicAtom):
        if 'atom' not in head.child_keys:
            return [] # Do nothing
        elif head.atom.ast_type == ASTType.BooleanConstant:
            return [] # Do nothing
        raise ValueError("All rule heads must be non-conditional simple literals")
    
    if head.sign == Sign.Negation:
        # Flip to body as integrity constriant
        head.sign = Sign.NoSign
        rule.body.append(deepcopy(head))
        rule.head = BooleanConstant(0)
        constraints.append(rule)
    elif head.sign == Sign.NoSign and head.atom.symbol.ast_type == ASTType.UnaryOperation and head.atom.symbol.operator_type == UnaryOperator.Minus:
        # -a(X) -> new constraints!!!
        constraints.append(Rule(
            location=rule.location,
            head = BooleanConstant(0),
            body = [
                deepcopy(head.atom.symbol),
                deepcopy(head.atom.symbol.argument)
            ] # -a and a cannot hold together!!
        ))
    return constraints

def preprocess(rule: AST) -> List[AST]:
    """Translate raw rule statement to preprocessed rule by...
    - Unpack OR statement aggregates
    - Unpack pooling
    - Convert numeric strings that share dimensions to integer
    - Add dual statements

    Args:
        rule (AST): String to parse. Might raise syntax error if parsing is failed

    Returns:
        List[AST]: _description_
    """

    new_rules = []

    if rule.ast_type == ASTType.Rule:
        unpacked_count_rules = unpack_count_aggregates(rule)
        
        unpooled_rules = []
        for rule in unpacked_count_rules:
            unpooled_rules.extend(rule.unpool())

        for t3 in unpooled_rules:
            # t3 = translate_numeric_string(t3)
            new_rules.append(t3)

            # Dual statements
            for dual in get_dual(t3):
                new_rules.append(dual)
            # not pred :- -pred DISABLED TO PREVENT INFINITE LOOPS
            for explicit_dual in get_explicit_dual(t3):
                new_rules.append(explicit_dual)
            # :- a, -a
            for constraint in get_constraints(t3):
                new_rules.append(constraint)

    return new_rules