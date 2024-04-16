import re

def convert_body_text(body_text, dataset, world_model=None):
    """Split rules and facts for LAMBADA.

    Args:
        body_text (_type_): _description_
        dataset (_type_): _description_

    Returns:
        _type_: _description_
    """
    if dataset == "proofwriter_dep5" or dataset == "birdselectricity":
        # Split sents
        sents = body_text.split(". ")
        for i in range(len(sents)-1):
            sents[i] = sents[i] + "." # restore dots
        
        rules = []; facts = []
        for sent in sents:
            is_rule = False
            for rule_keyword in ["if", "all", "are", "some", "then"]:
                if rule_keyword in sent.lower():
                    is_rule = True
                    rules.append(sent)
                    break
            if not is_rule:
                facts.append(sent)
        return facts, rules
    if dataset == "pararules":
        # Split sents
        sents = body_text.split(". ")
        for i in range(len(sents)-1):
            sents[i] = sents[i] + "." # restore dots
        return sents, sents
    if dataset == "prontoqa":
        # Split sents
        sents = body_text.split(". ")
        for i in range(len(sents)-1):
            sents[i] = sents[i] + "." # restore dots
        
        rules = []; facts = []
        for sent in sents:
            is_rule = False
            for rule_keyword in ["are", "every", "each"]:
                if rule_keyword in sent.lower():
                    is_rule = True
                    rules.append(sent)
                    break
            if not is_rule:
                facts.append(sent)
        return facts, rules
    elif dataset == "ecthr" or dataset == "clutrr" or dataset == "stepgame":
        return body_text.strip().split("\n"), world_model.strip().split("\n")
    else:
        return body_text, body_text

def convert_body_text_for_symba(body_text, dataset):
    """Split rules and facts for SymBa.

    Args:
        body_text (_type_): _description_
        dataset (_type_): _description_

    Returns:
        _type_: _description_
    """
    if dataset == "proofwriter_dep5" or dataset == "birdselectricity":
        # Split sents
        sents = body_text.split(". ")
        for i in range(len(sents)-1):
            sents[i] = sents[i] + "." # restore dots
        
        rules = []; facts = []
        for sent in sents:
            is_rule = False
            for rule_keyword in ["if", "all", "are", "some", "then"]:
                if rule_keyword in sent.lower():
                    is_rule = True
                    rules.append(sent)
                    break
            if not is_rule:
                facts.append(sent)
        return " ".join(facts), " ".join(rules)
    elif dataset == "hotpotqa":
        # Split sents
        sents = body_text.split("Question: ")
        for i in range(len(sents)):
            sents[i] = sents[i].strip()
        
        rules = sents[:-1]; facts = [sents[-1]]
        return " ".join(facts), " ".join(rules)
    else:
        return body_text, body_text

def convert_goal(goal, dataset):
    """Covnert symbolic goal to natural language.

    Args:
        goal (_type_): _description_
        dataset (_type_): _description_

    Raises:
        Exception: _description_

    Returns:
        _type_: _description_
    """
    # Convert goal into natural language
    if dataset == "proofwriter_dep5" or dataset == "birdselectricity" or dataset == "pararules" or dataset == "prontoqa":
        match = re.match(r"(not |)([a-z_]+)\(([a-z_]+),\s?([a-z_]+)\)", goal)
        sign = match.group(1)
        verb = match.group(2)
        subj = match.group(3)
        obj = match.group(4)
        if verb == "is":
            sent = " ".join([subj, verb, sign, obj])
            sent = sent.replace("  ", " ")
            return sent.capitalize()
        else:
            if sign.strip(): # sign is not empty -> Negation
                sent = " ".join([subj, "does not", verb, obj])
                sent = sent.replace("  ", " ")
                return sent.capitalize()
            else:
                sent = " ".join([subj, verb, obj])
                sent = sent.replace("  ", " ")
                return sent.capitalize()
    elif dataset == "stepgame":
        print(goal)
        match = re.match(r"relativeDirection\(\"([A-Z])\", ([a-z_]+), \"([A-Z])\"\)", goal)
        per1 = match.group(1)
        rel = match.group(2).replace("_", "-")
        per2 = match.group(3)
        sent = f"{per1} is at the {rel} of {per2}."
        return sent.capitalize()
    elif dataset == "clutrr":
        match = re.match(r"relation\(([a-z_]+), ([a-z_]+), ([a-z_]+)\)", goal)
        per1 = match.group(1)
        rel = match.group(2)
        per2 = match.group(3)
        sent = f"{per1} can be inferred as the {rel} of {per2}."
        return sent.capitalize()
    elif dataset == "gsm8k":
        ans = re.match(r"answer\((.*)\)", goal).group(1)
        return ans
    elif dataset == "ecthr":
        return "This case results in a non-violation of the applicant’s right to a fair trial."
    raise ValueError("Undefined dataset")