import argparse
import json
from pathlib import Path

from knowgraph.config import get_settings
from knowgraph.graph import GraphStore
from knowgraph.ingestion import ingest, parse_json


def main():
    parser = argparse.ArgumentParser(description="KnowGraph data tools")
    parser.add_argument("command", choices=["seed", "stats"])
    parser.add_argument("--file", type=Path, default=Path("data/demo.json"))
    parser.add_argument(
        "--only-if-empty",
        action="store_true",
        help="Skip automatic seeding when graph records already exist",
    )
    args = parser.parse_args()
    store = GraphStore(get_settings())
    try:
        store.initialize()
        if args.command == "seed":
            if args.only_if_empty and store.counts()["nodes"]:
                print(json.dumps({"skipped": True, "reason": "Graph already contains records"}))
                return
            result = ingest(store, parse_json(args.file.read_bytes()))
            print(result.model_dump_json(indent=2))
            if result.rejected:
                raise SystemExit(1)
        else:
            print(json.dumps(store.counts(), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
