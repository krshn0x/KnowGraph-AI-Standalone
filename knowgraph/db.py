from falkordb import FalkorDB

from knowgraph.config import settings


def connect():
    """Return the configured FalkorDB graph handle."""
    client = FalkorDB(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        username=settings.falkordb_username,
        password=settings.falkordb_password,
    )
    return client.select_graph(settings.falkordb_graph)


def check_connection(graph=None) -> bool:
    graph = graph or connect()
    result = graph.query("RETURN 1 AS connected")
    return bool(result.result_set and result.result_set[0][0] == 1)
