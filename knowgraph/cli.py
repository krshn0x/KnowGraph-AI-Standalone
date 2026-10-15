import argparse

from knowgraph.db import check_connection, connect
from knowgraph.seed import seed_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="KnowGraph graph foundation commands")
    parser.add_argument("command", choices=("check", "seed"))
    args = parser.parse_args()
    graph = connect()
    if args.command == "check":
        print("FalkorDB connection OK" if check_connection(graph) else "FalkorDB connection failed")
    else:
        print(seed_graph(graph))


if __name__ == "__main__":
    main()
