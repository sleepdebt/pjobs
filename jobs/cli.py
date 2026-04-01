import click
from rich.console import Console

from jobs.config import load_config, init_config, open_config_in_editor
from jobs.search import search_jobs, SOURCES
from jobs.display import print_results, print_sources, print_searching

console = Console()


@click.group()
def cli():
    """
    Find product leadership job listings from ATS platforms.

    Searches Ashby, Lever, and Greenhouse for roles like VP of Product,
    Head of Product, Director of Product — listings that often never make
    it to LinkedIn or Indeed.
    """
    pass


@cli.command()
@click.argument("title", required=False, default=None)
@click.option(
    "--since",
    default=None,
    metavar="TIMEFRAME",
    help="Only show listings posted within this window. Examples: 24h, 3d, 7d, 30d",
)
def search(title: str | None, since: str | None):
    """
    Search for job listings.

    With no arguments, searches using your configured default titles.
    Pass a TITLE to search for a specific role instead.

    \b
    Examples:
      jobs search
      jobs search "Chief Product Officer"
      jobs search --since 24h
      jobs search "Head of Product" --since 7d
    """
    config = load_config()
    sources = config.get("sources", ["ashby", "lever", "greenhouse"])
    serpapi_key = config.get("serpapi_key") or None

    # Use provided title or fall back to configured defaults
    titles = [title] if title else config.get("titles", [])

    if not titles:
        console.print("\n  [yellow]No titles configured.[/yellow] Add some to your config:")
        console.print("  [dim]jobs config[/dim]\n")
        return

    print_searching(titles, since)

    try:
        results = search_jobs(titles, sources, since=since, serpapi_key=serpapi_key)
    except Exception as e:
        console.print(f"\n  [red]Search failed:[/red] {e}\n")
        return

    print_results(results, since=since)


@cli.command()
def config():
    """Open your config file in $EDITOR.

    Config lives at ~/.jobs/config.yaml. Edit your default titles,
    sources, and optionally add a SerpAPI key for more reliable results.
    """
    path = init_config()
    console.print(f"\n  [dim]Opening config: {path}[/dim]\n")
    open_config_in_editor()


@cli.command()
def sources():
    """List the ATS sources being searched."""
    cfg = load_config()
    active = cfg.get("sources", list(SOURCES.keys()))
    print_sources(active)
