import json
import os
from pathlib import Path
from types import SimpleNamespace
# from pysolver.utils import parse_line, find_all_const

class HiereasonContext():
    def __init__(self, method: str, config: SimpleNamespace, dataset: str):
        self.config: SimpleNamespace = config.hiereason
        self.dataset: str = dataset

        dataset_dir = Path(self.config.datasets.__dict__[dataset])
        self.ontology_data = []
        self.example_data = []
        self.world_data = []
        self.test_data = None

        self.current_rules = []
        
        # Optional
        if "world_data.json" in os.listdir(dataset_dir):
            self.world_data = json.load(open(dataset_dir / "world_data.json"))
        # Mandatory
        self.test_data = json.load(open(dataset_dir / "test_data.json"))
        self.prompt_data = json.load(open(dataset_dir / "prompt_data.json"))[method]

        self._validate_data()
    
    def _validate_data(self):
        self._validate_ontology_data()
        self._validate_example_data()
        self._validate_world_data()
        self._validate_test_data()

    def _validate_ontology_data(self):
        data = self.ontology_data
        if data is None:
            return
        assert isinstance(data, list)
        for datum in data:
            assert isinstance(datum, dict)
            for k in ["id", "const", "nargs", "description", "lexical_unit"]:
                assert k in datum
                
    def _validate_example_data(self):
        data = self.example_data
        if data is None:
            return
        assert isinstance(data, list)
        for datum in data:
            assert isinstance(datum, dict)
            for k in ["id", "statement", "description"]:
                assert k in datum

    def _validate_world_data(self):
        data = self.world_data
        if data is None:
            return
        assert isinstance(data, list)
        for datum in data:
            assert isinstance(datum, dict)
            for k in ["id", "name", "statements"]:
                assert k in datum
            for rule in datum["statements"]:
                for k in ["id", "statement", "description"]:
                    assert k in rule

    def _validate_test_data(self):
        data = self.test_data
        if data is None:
            return
        assert isinstance(data, list)
        for datum in data:
            assert isinstance(datum, dict)
            for k in ["id", "body_text", "world_model", "goal", "label", "program"]:
                assert k in datum

    # def find_missing_ontology(self, consts: List[AST]):
    def find_missing_ontology(self, consts):
        pass

    def add_rule(self, rule):
        self.current_rules.append(rule)