from rich.console import Console
from rich.text import Text
from rich.rule import Rule

console = Console(highlight=False)

SOURCE_COLORS = {
    "Ashby": "cyan",
    "Lever": "magenta",
    "Greenhouse": "green",
}


def print_results(results: list[dict], since: str | None = None):
    """Print job listings to the terminal in a clean, scannable format."""
    if not results:
        _print_empty(since)
        return

    console.print()
    console.print(Rule(style="dim"))

    for job in results:
        _print_job(job)

    console.print(Rule(style="dim"))
    console.print()

    label = f"[bold]{len(results)}[/bold] listing{'s' if len(results) != 1 else ''} found"
    if since:
        label += f" in the last [bold]{since}[/bold]"
    console.print(f"  {label}", style="dim")
    console.print()


def _print_job(job: dict):
    """Print a single job listing as a two-line card."""
    title = job.get("title") or job.get("searched_title") or "Unknown Role"
    company = job.get("company") or "Unknown Company"
    source = job.get("source") or ""
    url = job.get("url", "")

    source_color = SOURCE_COLORS.get(source, "white")

    # Line 1: Title · Company · Source badge
    line = Text()
    line.append(title, style="bold white")
    line.append("  ·  ", style="dim")
    line.append(company, style="bold")
    line.append("  ·  ", style="dim")
    line.append(source, style=source_color)

    console.print()
    console.print(f"  ", end="")
    console.print(line)

    # Line 2: URL (clickable in most modern terminals)
    console.print(f"  [dim]{url}[/dim]")


def _print_empty(since: str | None):
    """Print a helpful message when no results are found."""
    console.print()
    if since:
        console.print(
            f"  [dim]No listings found in the last [bold]{since}[/bold]. "
            f"Try a longer window, e.g. [bold]--since 7d[/bold][/dim]"
        )
    else:
        console.print("  [dim]No listings found. Try a different title or check your config.[/dim]")
    console.print()


def print_sources(sources: list[str]):
    """Print the list of active ATS sources."""
    from jobs.search import SOURCE_LABELS
    console.print()
    console.print("  [bold]Active sources:[/bold]")
    console.print()
    for s in sources:
        label = SOURCE_LABELS.get(s, s.capitalize())
        console.print(f"  [green]✓[/green]  {label}")
    console.print()


def print_searching(titles: list[str], since: str | None):
    """Print a status message while searching."""
    console.print()
    title_list = ", ".join(f'[bold]{t}[/bold]' for t in titles)
    msg = f"  Searching for {title_list}"
    if since:
        msg += f" · last [bold]{since}[/bold]"
    msg += " …"
    console.print(msg, style="dim")
