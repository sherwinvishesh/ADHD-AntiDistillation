import json
import os

_QUESTION_KEYS = ("input", "question", "prompt")
_QUESTION_PREFIX = "Question: "

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATASETS_DIR = os.path.join(_HERE, "datasets")


def resolve_dataset_path(name_or_path):
    """
    Accepts either a full/relative path or just a bare filename
    (e.g. "test_dataset.json") and resolves it to an actual file —
    checking the path as given first, then datasets/ within SPECTRE_Test.

    Raises FileNotFoundError if neither location has the file.
    """
    if os.path.isfile(name_or_path):
        return os.path.abspath(name_or_path)

    candidate = os.path.join(_DATASETS_DIR, name_or_path)
    if os.path.isfile(candidate):
        return candidate

    raise FileNotFoundError(
        f"Dataset not found: {name_or_path!r} "
        f"(also checked {_DATASETS_DIR})"
    )


def load_dataset(path):
    """
    Load a JSON dataset — a list of objects, each containing a question
    under one of "input", "question", or "prompt" (checked in that order).

    The sample datasets store questions under "input" prefixed with the
    literal "Question: " — that prefix is stripped if present.

    Returns a list of question strings.
    Raises ValueError with the actual keys found if none match.
    """
    with open(path) as f:
        data = json.load(f)

    if not isinstance(data, list) or not data:
        raise ValueError(f"{path}: expected a non-empty JSON list of objects")

    questions = []
    for i, row in enumerate(data):
        key = next((k for k in _QUESTION_KEYS if k in row), None)
        if key is None:
            raise ValueError(
                f"{path}: row {i} has none of the expected question keys "
                f"{_QUESTION_KEYS}. Found keys: {list(row.keys())}"
            )
        text = row[key]
        if text.startswith(_QUESTION_PREFIX):
            text = text[len(_QUESTION_PREFIX):]
        questions.append(text)

    return questions


def write_results(dataset_path, results, summary):
    """
    Write {"summary": ..., "results": ...} to
    <dataset_stem>_spectre_answers.json, right next to the input dataset
    (i.e. in the same folder it was loaded from).

    Returns the output path.
    """
    out_dir = os.path.dirname(os.path.abspath(dataset_path))
    stem = os.path.splitext(os.path.basename(dataset_path))[0]
    out_path = os.path.join(out_dir, f"{stem}_spectre_answers.json")

    with open(out_path, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    return out_path
