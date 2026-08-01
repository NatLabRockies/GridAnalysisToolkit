"""CLI commands for gat server, push, scenarios, and query."""

from __future__ import annotations

import click

# ============================================================
# Server commands
# ============================================================


@click.group("server")
def server():
    """Manage the GAT data server."""
    pass


@server.command("start")
@click.option("--host", default=None, help="Bind address (default: 127.0.0.1)")
@click.option(
    "--port", "-p", default=None, type=int, help="Listen port (default: 8815)"
)
@click.option("--db", "db_path", default=None, help="Path to DuckDB file")
@click.option("--token", default=None, help="Auth token (or set GAT_SERVER_AUTH_TOKEN)")
def server_start(host, port, db_path, token):
    """Start the GAT server (foreground)."""
    try:
        import uvicorn
    except ImportError:
        raise click.ClickException(
            "Server dependencies not installed. Run: pip install nlr-gat[server]"
        )

    from gat.server.config import ServerConfig

    config = ServerConfig.from_env(
        host=host,
        port=port,
        db_path=db_path,
        auth_token=token,
    )

    click.echo(f"Starting GAT server on {config.host}:{config.port}")
    click.echo(f"DuckDB: {config.db_path}")
    if config.auth_token:
        click.echo("Auth: enabled (bearer token)")
    else:
        click.echo("Auth: disabled")

    from gat.server.app import create_app

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


@server.command("status")
@click.option("--server", "server_url", default=None, help="Server URL")
def server_status(server_url):
    """Check if a GAT server is running."""
    url = _resolve_server_url(server_url)
    if url is None:
        click.echo("No server URL configured. Use --server or set GAT_SERVER.")
        return

    try:
        from gat.client import GATClient

        client = GATClient(url)
        info = client.health()
        click.echo(f"Server: {url}")
        click.echo(f"Status: {info.get('status', 'unknown')}")
        click.echo(f"Version: {info.get('version', 'unknown')}")

        scenarios = client.list_scenarios()
        click.echo(f"Scenarios: {len(scenarios)}")
    except Exception as e:
        click.echo(f"Server at {url} is not reachable: {e}")


# ============================================================
# Push command
# ============================================================


@click.command("push")
@click.argument("project")
@click.argument("scenario")
@click.option(
    "--handler", "-h", required=True, help="Handler type (sienna, reeds, plexos)"
)
@click.option("--system", "system_path", default=None, help="Path to system file")
@click.option(
    "--simulation",
    "simulation_paths",
    multiple=True,
    help="Path(s) to simulation files",
)
@click.option("--server", "server_url", default=None, help="Server URL")
def push_cmd(project, scenario, handler, system_path, simulation_paths, server_url):
    """Push a scenario for server-side ingestion."""
    url = _resolve_server_url(server_url)
    if url is None:
        raise click.ClickException(
            "No server URL. Use --server or set GAT_SERVER env var."
        )

    try:
        from gat.client import GATClient
    except ImportError:
        raise click.ClickException(
            "Client dependencies not installed. Run: pip install nlr-gat[client]"
        )

    client = GATClient(url)
    click.echo(f"Pushing {project}/{scenario} to {url}...")

    try:
        result = client.push(
            project=project,
            scenario=scenario,
            handler=handler,
            system_path=system_path,
            simulation_paths=list(simulation_paths) if simulation_paths else None,
        )
        click.echo(f"Status: {result.get('status', 'unknown')}")
        click.echo(f"Schema: {result.get('schema', 'unknown')}")
    except Exception as e:
        raise click.ClickException(f"Push failed: {e}")


# ============================================================
# Scenarios command
# ============================================================


@click.command("scenarios")
@click.option("--server", "server_url", default=None, help="Server URL")
def scenarios_cmd(server_url):
    """List materialized scenarios on the server."""
    url = _resolve_server_url(server_url)
    if url is None:
        raise click.ClickException(
            "No server URL. Use --server or set GAT_SERVER env var."
        )

    try:
        from gat.client import GATClient
    except ImportError:
        raise click.ClickException(
            "Client dependencies not installed. Run: pip install nlr-gat[client]"
        )

    client = GATClient(url)
    scenarios = client.list_scenarios()

    if not scenarios:
        click.echo("No scenarios materialized on the server.")
        return

    click.echo(f"{'Project':<20} {'Scenario':<20} {'Handler':<10} {'Status':<10}")
    click.echo("-" * 60)
    for s in scenarios:
        click.echo(
            f"{s['project']:<20} {s['scenario']:<20} "
            f"{s['handler']:<10} {s['status']:<10}"
        )


# ============================================================
# Query command
# ============================================================


@click.command("query")
@click.argument("project")
@click.argument("scenario")
@click.argument("sql")
@click.option("--server", "server_url", default=None, help="Server URL")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "csv", "json"]),
)
def query_cmd(project, scenario, sql, server_url, output_format):
    """Execute SQL against a remote scenario."""
    url = _resolve_server_url(server_url)
    if url is None:
        raise click.ClickException(
            "No server URL. Use --server or set GAT_SERVER env var."
        )

    try:
        from gat.client import GATClient
    except ImportError:
        raise click.ClickException(
            "Client dependencies not installed. Run: pip install nlr-gat[client]"
        )

    client = GATClient(url)
    remote = client.scenario(project, scenario)

    try:
        df = remote.sql(sql)
    except Exception as e:
        raise click.ClickException(f"Query failed: {e}")

    if output_format == "csv":
        click.echo(df.to_csv(index=False))
    elif output_format == "json":
        click.echo(df.to_json(orient="records", indent=2))
    else:
        click.echo(df.to_string(index=False))


# ============================================================
# Helpers
# ============================================================


def _resolve_server_url(cli_url: str | None) -> str | None:
    """Resolve server URL: CLI flag > env var > user config > None."""
    import os

    if cli_url:
        return cli_url

    env_url = os.environ.get("GAT_SERVER")
    if env_url:
        return env_url

    # Try user config
    try:
        from gat.models.user import load_user_config

        config = load_user_config()
        if hasattr(config, "server_url") and config.server_url:
            return config.server_url
    except Exception:
        pass

    return None
