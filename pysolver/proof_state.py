from typing import List, Tuple, Dict, Any
from copy import deepcopy, copy
import re
from clingo.ast import *

from .utils import flip_sign, is_negated, get_hash_head, parse_line, anonymize_vars
from .unify import bind, find_bindings, equivalent
from .preprocess import preprocess

class ProofContext():
    def __init__(self):
        """A global context manager that runs through a proof.
        Stores current rules, variable re-indexing information, and more.

        Program contains a dictionary (JSON-compatible) of rules.
        Mandatory keys:
        - `asp` : contains a string version of the logic program.

        ex. [{'asp': 'a :- b, c(X).', 'comment': 'if b holds and c holds for any X, a holds.'}]
        """
        self.program: List[Dict[str, Any]] = []
        # Preprocess programs (add dual, split OR statements,...)
        self.preprocessed_program: List[AST] = []
        
        # Hashed dictionary for fast retrieval of rules
        self.rule_dict: Dict[str, List[AST]] = {}

        # Hashed dictionary for fast retrieval of proofs
        self.proof_dict: Dict[str, List[AST]] = {}

        # Global index for rule instantiation.
        self.variable_index: int = 0

    def add_rule(self, line: Dict[str, Any]) -> None:
        self.program.append(line)
        
        # Parse string to AST
        assert "statement" in line
        rule = parse_line(line["statement"])
        preprocessed_rule = preprocess(rule)
        
        # Add to preprocessed program list
        self.preprocessed_program.extend(preprocessed_rule)
        
        # Add to rule dict (for fast finding)
        for rule in preprocessed_rule:
            hash_head = get_hash_head(rule)
            if hash_head not in self.rule_dict:
                self.rule_dict[hash_head] = []
            
            # Check for duplicates
            is_dup = False
            # FIXME
            # for existing_rule in self.rule_dict[hash_head]:
            #     if find_bindings(rule, existing_rule):
            #         is_dup = True
            if not is_dup:
                self.rule_dict[hash_head].append(rule)

    def find_rule(self, goal: AST):
        hash_head = get_hash_head(goal)
        if hash_head not in self.rule_dict:
            return []
        relevant_rules = self.rule_dict[hash_head]
        result = []
        for rule in relevant_rules:
            head = rule.head
            if find_bindings(head, goal) is not None:
                result.append(deepcopy(rule))
        return result

    def reindex_variables(self, rule):
        class VariableReindexer(Transformer):
            def __init__(self, variable_idx):
                super(VariableReindexer, self).__init__()
                self.variable_idx = variable_idx
                self.anonym_idx = 0

            def visit_Variable(self, node):
                if node.name == "_":
                    # anonymous variable
                    node.name = f"_Anon_{self.variable_idx}_{self.anonym_idx}"
                    self.anonym_idx += 1
                else:
                    node.name = node.name + f"_{self.variable_idx}"
                return node
        # Re-index
        indexer = VariableReindexer(self.variable_index)
        rule = indexer(deepcopy(rule))
        self.variable_index += 1
        return rule

    def add_proof(self, goal, proof):
        key = str(anonymize_vars(goal))
        self.proof_dict[key] = proof
    def get_proof(self, goal):
        key = str(anonymize_vars(goal))
        return self.proof_dict.get(key, None)

class ProofState():
    def __init__(self, goal: AST):
        assert goal.ast_type == ASTType.Literal
        self.original_goal = goal
        self.proved = False
        self.parent: ProofState = None
        # Bindings
        self.goal = deepcopy(goal)
        self.bindings: Dict[AST, AST] = {}
        self.rule_hash: int = None
        # Children
        self.proof: List[ProofState]= [] # proved


    def get_root(self):
        curr_state = self
        while curr_state.parent is not None:
            curr_state = curr_state.parent
        return curr_state
    def depth(self) -> int:
        curr_state = self
        depth = 0
        while curr_state.parent is not None:
            curr_state = curr_state.parent
            depth += 1
        return depth

    def detect_loop(self) -> str:
        goal = self.goal
        if is_negated(goal):
            goal = flip_sign(goal)
        loop_found = False
        positive_loop = False
        
        # Find loop in parents
        # Constraint Answer Set Programming Without Grounding - Appendix B
        curr_state = self.parent
        negation_count = 0
        while curr_state is not None:
            curr_goal = curr_state.goal
            if is_negated(curr_goal):
                negation_count += 1
                curr_goal = flip_sign(curr_goal)
            # Found a loop
            if equivalent(curr_goal, goal) and self.rule_hash == curr_state.rule_hash:
                # Check for variables
                loop_found = True
                break
            curr_state = curr_state.parent
        # Return result
        if loop_found:
            if is_negated(goal):
                return "success"
            elif negation_count > 0 and negation_count % 2 == 0:
                return "success"
            else:
                return "failure"
        else:
            return "none"

    def __str__(self) -> str:
        return self._pprint(indent=0)
    def _pprint(self, indent: int) -> str:
        string = "  " * indent
        string += f"{str(self.goal)}\n"
        # Proved subgoals
        for subgoal in self.proof:
            string += subgoal._pprint(indent+1)
        return string

    def add_proof(self, proof):
        self.proved = True
        self.proof = proof

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k in ["parent", "proof", "bindings"]:
                setattr(result, k, copy(v)) # Shallow copy to prevent infinite recursion
            else:
                setattr(result, k, deepcopy(v, memo))
        return result