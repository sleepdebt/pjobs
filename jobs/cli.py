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

    Searches Ashby, Lever, Greenhouse, Wellfound, and BuiltIn for roles like
    VP of Product, Head of Product, Director of Product — listings that often
    never make it to LinkedIn or Indeed.
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
@click.option(
    "--location",
    default=None,
    metavar="LOCATION",
    help="Filter by location. Overrides config. Examples: 'remote', 'New York', 'United States'",
)
def search(title: str | None, since: str | None, location: str | None):
    """
    Search for job listings.

    With no arguments, searches using your configured default titles and locations.
    Pass a TITLE to search for a specific role instead.

    \b
    Examples:
      pjobs search
      pjobs search "Chief Product Officer"
      pjobs search --since 24h
      pjobs search --location remote
      pjobs search "Head of Product" --since 7d --location "New York"
    """
    config = load_config()
    sources = config.get("sources", ["ashby", "lever", "greenhouse", "wellfound", "builtin"])
    serpapi_key = config.get("serpapi_key") or None

    # Use provided title or fall back to configured defaults
    titles = [title] if title else config.get("titles", [])

    # Use --location flag if provided, otherwise fall back to config locations
    if location:
        locations = [location]
    else:
        locations = config.get("locations") or []

    if not titles:
        console.print("\n  [yellow]No titles configured.[/yellow] Add some to your config:")
        console.print("  [dim]pjobs config[/dim]\n")
        return

    print_searching(titles, since, locations=locations)

    try:
        results = search_jobs(
            titles,
            sources,
            since=since,
            locations=locations or None,
            serpapi_key=serpapi_key,
        )
    except Exception as e:
        console.print(f"\n  [red]Search failed:[/red] {e}\n")
        return

    print_results(results, since=since)


@cli.command()
def config():
    """Open your config file in $EDITOR.

    Config lives at ~/.jobs/config.yaml. Edit your default titles, locations,
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
