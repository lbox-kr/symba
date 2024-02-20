from typing import List, Dict
from copy import deepcopy
import logging

from clingo.ast import *
from clingo.control import *
from clingo.symbol import *
from clingo.solving import *

from .utils import is_negated, is_ground, flip_sign, UnprovedGoalState, parse_line, evaluate_num, convert_numeric_string_to_number
from .unify import find_bindings, bind
from .proof_state import ProofContext, ProofState

def consistency_check(context: ProofContext):
    false_lit = parse_line("#false.").head # retrieve literal `#false`
    if len(context.find_rule(false_lit)) == 0:
        return True
    if recursive_solve(ProofState(false_lit), context):
        return False
    return True

def solve(goal: AST, context: ProofContext, unproved_callback=None) -> List[ProofState]:
    # print(f"Start proof for {goal}")

    # Consistency check
    if not consistency_check(context):
        return []
    
    # Depth-first search (with explicit state) for a vaild proof
    root = ProofState(deepcopy(goal))
    result = recursive_solve(root, context, unproved_callback)
    return result


def recursive_solve(state: ProofState, context: ProofContext, unproved_callback = None) -> List[ProofState]:
    # state: pointer to the current goal in the full proof
    goal = state.goal

    ##### Cache proofs for speedup #####
    cached_proofs = context.get_proof(goal)
    if cached_proofs is not None:
        cached_proofs = deepcopy(cached_proofs)
        for c in cached_proofs:
            c.bindings = find_bindings(goal, c.goal) # rebind since variable names differ from cached goal and current goal
            c.rule_hash = state.rule_hash # Track history of which rule derived the state.goal from state.parent.goal
            c.parent = state.parent
        return cached_proofs
    ##### 1. Check coinduction (loop in proofs) #####
    result_str = state.detect_loop()
    if result_str == "success": # even>=2 negation
        # Goal is grounded & already proved in state (coinduction success)
        # print("Coinduction success")
        state.proved = True
        return [state]
    elif result_str == "failure": # 0 or odd>=1 negations
        # Goal clashes with other proved goal (coinduction failure)
        # print("Coinduction failure")
        return []
    else: # result == "none"
        # Neither coinduction success or failure
        pass

    ##### 2. Check comparison and assignment operators #####
    if goal.atom.ast_type == ASTType.BooleanConstant:
        if goal.atom.value:
            state.proved = True # Bind two literals
            state.bindings = {} # nothing to bind
            return [state]
        else:
            return []
    if goal.atom.ast_type == ASTType.Comparison:
        # Decompose comparison
        # (lterm) (guard (op) (rterm))
        lterm = evaluate_num(goal.atom.term)
        if len(goal.atom.guards) != 1:
            # Ill-formed comparison (e.g. A = B < C)
            return []
        guard = goal.atom.guards[0]
        op = guard.comparison
        rterm = evaluate_num(guard.term)
        if op == ComparisonOperator.Equal:
            # Equal : treat with `unify`
            bindings = find_bindings(lterm, rterm)
            if bindings is not None:
                # state = deepcopy(state)
                bind(state.goal, bindings)
                state.proved = True # Bind two literals
                state.bindings = bindings
                return [state]
            else:
                return []
        elif op == ComparisonOperator.NotEqual:
            bindings = find_bindings(lterm, rterm)
            if bindings is None:
                state.proved = True # Bind two literals
                state.bindings = {}
                return [state]
            else:
                return []
        else:
            # Greater/Less : only make sense if ground integers are compared
            if not is_ground(goal):
                # Comparison goal not grounded -> fail to prove anything
                return []
            lterm = lterm.symbol # Extract clingo.Symbol values
            rterm = rterm.symbol
            # Format check
            if not (lterm.type == rterm.type == SymbolType.String):
                # If attempting to compare anything else than a string -> FAIL
                return []
            lterm = convert_numeric_string_to_number(lterm.string)
            rterm = convert_numeric_string_to_number(rterm.string)
            if isinstance(lterm, str) or isinstance(rterm, str):
                # One of the operands is not a number but a plain string e.g. "Hello" -> FAIL
                return []
            # Finally, we compare...
            if op == ComparisonOperator.GreaterThan and lterm > rterm or \
                op == ComparisonOperator.GreaterEqual and lterm >= rterm or \
                op == ComparisonOperator.LessThan and lterm < rterm or \
                op == ComparisonOperator.LessEqual and lterm <= rterm:
                    state.proved = True
                    return [state]
            else:
                return []
        # Comparison clear!!

    ##### 3. Check classic negation (not x) #####
    if is_negated(goal):
        new_goal = deepcopy(state.goal)
        new_goal.sign = Sign.NoSign
        new_proved_states = recursive_solve(ProofState(new_goal), context, unproved_callback)
        if len(new_proved_states) >= 1:
            # TODO add callback for trace failure
            # print(goal, "failed because", new_goal, "is proved")
            context.add_proof(goal, [])
            return []
        else:
            # print(goal, "suceeded because", new_goal, "cannot be proved")
            pass

    ##### 4. Check rules and facts #####
    
    proved_states = [] # result list

    # Head is plain literal(function, const, ..) -> Find relevant rules
    rules = context.find_rule(goal)
    original_state = state # preserve original state to prevent mix between rules
    is_any_rule_unified = len(rules) > 0

    # apply rules recursively
    for rule in rules:
        rule_hash = rule.__hash__() # hash before reindexing
        # Check if goal unifies with rule head, and get variable mapping
        rule = context.reindex_variables(rule) # deepcopy

        bindings = find_bindings(rule.head, goal)
        if bindings is None:
            continue # unification failure(rule head does not match current goal)
        else:
            is_any_rule_unified = True
        # State base to proof
        state = deepcopy(original_state)
        bind(state.goal, bindings)
        bind(rule, bindings)
        state.bindings = bindings

        # Add binding information created by rules
        if len(rule.body) == 0:
            # fact, without rule body
            state.add_proof([])
            proved_states.append(state)
        else: # len(rule.body) >= 1
            # Recursively apply the rules
            # Set new goal and register to current state
            
            # Variable naming convention
            # target_state          subset  bodygoal  (not yet seen)
            # a               :-    b,      c,        d.
            # iter1. subset: [], bodygoal: b
            # iter2. subset: [b], bodygoal: c
            # iter3. subset: [b, c], bodygoal: d

            body_subset_proofs = [(state, [], bindings)]
            # subgoal_cache = {} # Cache results to prevent exponential explosion if many possibilities exist
            for i in range(len(rule.body)):
                bodygoal = deepcopy(rule.body[i])

                new_body_subset_proofs = []

                for target_state, subset_proof, curr_bindings in body_subset_proofs:
                    curr_bodygoal = deepcopy(bodygoal)
                    bind(curr_bodygoal, curr_bindings)
                    # bind to current bindings
                    # Prove partially bound subgoals
                    new_state = ProofState(curr_bodygoal)
                    new_state.parent = state
                    new_state.rule_hash = rule_hash
                    new_state_proofs = recursive_solve(new_state, context, unproved_callback)
                    # subgoal_cache[curr_bodygoal] = new_state_proofs

                    # Extend subset (list of already proven goals) with fresh proved goal
                    for new_proof in new_state_proofs: # Each ProofStates contain single binding
                        # deepcopy to prevent crashing
                        new_target_state = deepcopy(target_state)
                        new_curr_proof = subset_proof + [new_proof] # Extend subset
                        new_binding = deepcopy(curr_bindings)
                        new_binding.update(new_proof.bindings)
                        new_body_subset_proofs.append((new_target_state, new_curr_proof, new_binding))
                
                # update body_subset_proofs
                body_subset_proofs = new_body_subset_proofs
            # garbage collection
            # del subgoal_cache
            
            for target_state, proof, final_binding in body_subset_proofs:
                target_state.add_proof(proof)
                bind(target_state.goal, final_binding)
                target_state.bindings = final_binding
                proved_states.append(target_state)
                
    # Recover original state
    state = original_state
    
    # proved!
    if len(proved_states) > 0:
        state.proved = True
    # handle negation: if reach here, it is true
    if is_negated(goal) and not is_any_rule_unified:
        # not x
        # where x does not exists
        state.proved = True
        proved_states.append(state)

    ##### 5. Post-tasks: add to cache, failure callback #####

    # Track unproved goals by callback
    if unproved_callback is not None:
        call_parent = False
        if not state.proved:
            if not is_any_rule_unified:
                call_parent = unproved_callback(state, UnprovedGoalState.UNPROVED_YET) # No rules that unify with a positive goal
            else:
                call_parent = unproved_callback(state, UnprovedGoalState.BACKTRACK) # Despite rules exist, 
        elif state.proved and is_negated(state.goal) and not is_any_rule_unified:
            # `not x` is proved because `x` cannot be proved
            flipped_state = deepcopy(state)
            flipped_state.goal = flip_sign(flipped_state.goal)
            call_parent = unproved_callback(flipped_state, UnprovedGoalState.NOT_EXIST) # Although `not x` is considered as proved, need to check x
        
        # Since unproved_callback can modify global context (rule_dict, replay consistency check, ...)
        # ex.
        #   - context.add_rule(rule)
        # Re-call recursive_solve() with current goal
        if call_parent:
            proved_states = recursive_solve(state, context, unproved_callback)

    context.add_proof(goal, proved_states)
    return proved_states