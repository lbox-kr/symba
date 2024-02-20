This is the data used in the paper "SymBa: Symbolic Backward Chaining for Multi-step Natural Language Reasoning."

Each folder, named after respective datasets, contains the followings:
- `test_data.json` : Test split data
- `prompt_data.json`: Prompt data used for each methods
- (optional) `world_data.json`: Expert system rules used for SymBa.

Note 1.
`error_analysis_data` contains the data used for Section 6.1 (Error analysis), the Rule Search Recall experiment for bound and unbound rules. First 330 examples are for bound rules, while the other 330 are for unbound rules.

Note 2.
Prompts used for ablation study is also included in the `prompt_data.json` for each study.
However, -Unify cannot be seen here as it manipulates the Symbolic Validation step (that does not use LLMs).