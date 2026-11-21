"""Fail on any YAML file that is empty, does not parse, or repeats a key in one mapping."""
import pathlib
import sys

import yaml


class StrictLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep)


def check(path: pathlib.Path) -> str | None:
    text = path.read_text()
    try:
        documents = [document for document in yaml.load_all(text, Loader=StrictLoader)]
    except yaml.YAMLError as error:
        return str(error).replace("\n", " ")
    if not any(document is not None for document in documents):
        return "empty file"
    return None


def main(roots: list[str]) -> int:
    files = sorted({
        path
        for root in roots
        for path in (
            pathlib.Path(root).rglob("*.y*ml") if pathlib.Path(root).is_dir() else [pathlib.Path(root)]
        )
        if ".git" not in path.parts
    })
    failed = False
    for path in files:
        problem = check(path)
        if problem:
            failed = True
            print(f"{path}: {problem}")
    print(f"checked {len(files)} files")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["."]))
