from typing import List, Dict
from copy import deepcopy
import re
from collections import defaultdict

from clingo.ast import *
from clingo.control import *
from clingo.symbol import *
from .proof_state import ProofState
from .utils import anonymize_vars

class JustificationTreeNode():
    def __init__(self, repr: str):
        self.repr = repr
        self.children = []
        self._children_group = []
        self._group = 1 # siblings with same group consist parent group
        self.parent = None
    
    def add_child(self, child, nongroup=False):
        self.children.append(child)
        if nongroup:
            self._children_group.append(-1)
        else:
            self._children_group.append(self._group)
        assert len(self.children) == len(self._children_group)

        child.parent = self
    
    def group_finish(self):
        self._group += 1

    def remove_child(self, repr):
        remove_ids = [
            i for i, c in enumerate(self.children) if c.repr == repr
        ]
        for remove_id in remove_ids:
            self.children.pop(remove_id)
            self._children_group.pop(remove_id)
            assert len(self.children) == len(self._children_group)
    
    def _pprint(self, continuous, group):
        # Set tree-formatted prefix
        prefix = ""
        for cont in continuous[:-1]:
            prefix += "│ " if cont else "  "
        if continuous[-1]:
            prefix += "├ "
        else:
            prefix += "└ "
        # If OR-conjunction is present, add group info
        if group >= 0:
            group_str = f"({group}) "
        else:
            group_str = ""
        # Print prefix
        pp = prefix + group_str + self.repr + "\n"
        is_multiple_groups = len(set(self._children_group)) > 1
        for i, (child, group) in enumerate(zip(self.children, self._children_group)):
            if i < len(self.children) - 1:
                pp += child._pprint(continuous + [True], group if is_multiple_groups else -1)
            else:
                pp += child._pprint(continuous + [False], group if is_multiple_groups else -1)
        return pp

    def _transform(self, function):
        # Postorder transformation
        for child in self.children:
            child._transform(function) # Propagate to children first to prevent infinite recursion
        function(self) # Transform myself

    def __str__(self):
        return self.repr
    def __repr__(self):
        return "`" + self.repr + "`"

class JustificationTree():
    def __init__(self, proofs: List[ProofState]):
        if proofs is None:
            # Empty tree list
            return

        self.root = JustificationTreeNode("")
        bfs = [(proofs, self.root)]
        # bfs on state to traverse all nodes
        while len(bfs) > 0:
            proofs, parent_node = bfs.pop(0)

            # Group proofs by goal
            unique_goals = defaultdict(list)
            for state in proofs:
                unique_goals[anonymize_vars(str(state.goal))].append(state)

            for goal, states_per_goal in unique_goals.items():
                # Add a child node
                node = JustificationTreeNode(goal)
                parent_node.add_child(node)

                # Group proofs by rules
                substates_per_rule = {}
                for state in states_per_goal:
                    if len(state.proof) == 0:
                        # BFS Base case - Proved without rule induction
                        pass
                    else:
                        # BFS Propagation
                        # Collect subgoals per rule index
                        # a :- b(X), c(X) -> group all b(X), group all c(X)
                        if state.proof[0].rule_hash not in substates_per_rule:
                            substates_per_rule[state.proof[0].rule_hash] = [list() for _ in state.proof]
                        for idx, substate in enumerate(state.proof):
                            substates_per_rule[state.proof[0].rule_hash][idx].append(substate)
                # BFS Proceed (group same rules together)
                for rule, substates_per_idx in substates_per_rule.items():
                    for ith_goals in substates_per_idx:
                        bfs.append((ith_goals, node))
        
        if len(self.root.children) == 1:
            self.root = self.root.children[0]
    
    def __str__(self):
        result_str = self.root._pprint([False], -1)
        return anonymize_vars(result_str)

    def transform(self, function):
        self.root._transform(function)

    def find_node(self, node_seq):
        # Starts with first level(not root)
        node = self.root
        for node_rep in node_seq:
            new_node = None
            for child in node.children:
                if child.repr == node_rep:
                    new_node = child
            if new_node is not None:
                node = new_node
            else:
                # raise KeyError("Cannot find key " + node_rep + " in " + str(node_seq))
                return None
        return node
