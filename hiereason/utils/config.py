import yaml
import json
import os
from types import SimpleNamespace
import logging
import logging.handlers
from datetime import datetime

hiereason_config = None
_raw_hiereason_config = None

_logging_level = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

def load_config(dataset):
    global hiereason_config, _raw_hiereason_config

    path = os.environ.get("HIEREASON_CONFIG", "./hiereason_config.yaml")
    with open(path, "r", encoding="UTF-8") as config_file:
        _raw_hiereason_config = yaml.safe_load(config_file.read())

    # Convert to SimpleNamespace to access with a.b.c style notations instead of dict
    def load_object(_raw_hiereason_config):
        return SimpleNamespace(**_raw_hiereason_config)
    hiereason_config = json.loads(json.dumps(_raw_hiereason_config), object_hook=load_object)
    return hiereason_config

def set_logger(task: str, dataset: str = None, directory="logs/", level="info"):
    time = datetime.now().strftime("%Y%m%d-%H:%M:%S")
    filename = task + "_" + time + ("" if dataset is None else "_" + dataset) + ".log"

    try:
        # Set global logger
        logging.basicConfig(level=_logging_level[level])
    except KeyError:
        logging.error(f"Cannot find config level `{level}`: try in {_logging_level.keys()}")
    
    f = logging.Formatter(fmt='%(levelname)s:%(name)s: %(message)s '
    '(%(asctime)s; %(filename)s:%(lineno)d)',
    datefmt="%Y-%m-%d %H:%M:%S")
    handlers = [
        logging.FileHandler(
            os.path.join(directory, filename),
            encoding='utf8',
        ),
        logging.StreamHandler()
    ]
    root_logger = logging.getLogger()
    root_logger.setLevel(_logging_level[level])
    root_logger.handlers.clear()
    for h in handlers:
        h.setFormatter(f)
        h.setLevel(_logging_level[level])
        root_logger.addHandler(h)

    logging.info("Load config / set logger complete")
    logging.info("\n" + yaml.dump(_raw_hiereason_config) + "\n")