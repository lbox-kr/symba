# SymBa: Symbolic Backward Chaining for Multi-step Natural Language Reasoning

This is the repository for the following paper:

> Jinu Lee, Wonseok Hwang. (2024) SymBa: Symbolic Backward Chaining for Multi-step Natural Language Reasoning. [arXiv preprint](https://arxiv.org/abs/2402.12806).

## Installation

First, clone this repository and enter the directory.
```sh
git clone https://github.com/lbox-kr/symba.git
cd symba
```

Next, install necessary packages using the following script. (Note: virtual environment in highly recommended.)

```sh
pip -r requirements.txt
```

Then, copy the `hiereason_config_template.yaml` and rename it to `hiereason_config.yaml`. Open the file, and replace `sk-...` with your own OpenAI API key.

## Run experiments

Scripts that can run experiments are stored as `hiereason/run_*.py`. For example, to run SymBa on the ProofWriter-dep5 dataset, run the following script:

```sh
python hiereason/run_symba.py --dataset proofwriter_dep5
```

Values for the `--dataset` argument are the folder names in `data/`, which are:
- `proofwriter_dep5`, `birdselectricity`, `gsm8k`, `clutrr`, `ecthr`

You can find the experiment logs in `logs/` directory.

## Code anatomy

To deeply understand how SymBa works, we suggest to first take a look about how a _top-down solver_ works. While we describe the solver's mechanism with detail in Appendix A from our paper, we also recommend this material:
- [Slides from Uni Halle](https://users.informatik.uni-halle.de/~brass/lp21/print/c5_sldre.pdf)

The `pysolver` directory includes a self-contained top-down solver. It implements the SLDNF-resolution algorithm with miscellaneous utilities (goal tabling, OLON, ...). Note that we borrow the Answer Set Programming library, Clingo, for (only) parsing logical statements. The basic example for the logic program is presented in `pysolver/run_proof.py`. You may test the code by running the following:
```sh
python -m pysolver.run_proof
```

The __main algorithm__ (Algorithm 1 in the paper) is defined in pysolver/solve.py. The callback logic for single-step statement generation is implemented from # 5. Post-tasks: add to cache, failure callback. This part of the code activates only when the unproved_callback parameter is provided.

The modular __single-statement generation__ process is defined in `hiereason/symba/_symba.py`. Prompts for the tested methods can be found in `data/(dataset name)/prompt_data.json`.
