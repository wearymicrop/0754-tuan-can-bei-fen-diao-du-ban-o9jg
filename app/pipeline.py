from .config import RULESET
from .source import load_sample, validate
from .workflow import STAGES, TABLES


def evaluate(document, through=None):
    source = validate(document, TABLES)
    sections = {}
    for name, stage in STAGES:
        sections[name] = stage(source, sections)
        if through == name:
            return sections[name]
    return {"batch": source["batch"], "at": source["at"], "ruleset": RULESET, **sections}


def preview(sample, through=None):
    return evaluate(load_sample(sample), through)
