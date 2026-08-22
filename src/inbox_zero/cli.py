"""Interactive Command-Line Interface for inbox-zero using Typer and Rich."""

from __future__ import annotations

import json
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from inbox_zero.analyzer import analyze_email
from inbox_zero.client import GWSClient, GWSClientError
from inbox_zero.models import TriageBatch, TriageItem

app = typer.Typer(
    name="inbox-zero",
    help="AI & Deterministic Email Triage, Action Items & Calendar Manager using gws.",
    add_completion=False,
)
console = Console()


@app.command()
def scan(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum unread emails to scan."),
    query: str = typer.Option("is:unread", "--query", "-q", help="Gmail search filter query."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON for AI agents/scripts."),
) -> None:
    """Scan unread emails, extract summaries, action items, and calendar dates."""
    client = GWSClient()
    with console.status("[bold green]Scanning unread emails via gws...[/bold green]"):
        try:
            unread_list = client.list_unread_messages(max_results=limit, query=query)
        except GWSClientError as err:
            console.print(f"[bold red]Failed to fetch unread messages:[/bold red] {err}")
            raise typer.Exit(code=1)

    if not unread_list:
        console.print("[green]🎉 Inbox Zero! No unread messages found matching query.[/green]")
        return

    items: list[TriageItem] = []
    with console.status(f"[bold blue]Analyzing {len(unread_list)} emails...[/bold blue]"):
        for m in unread_list:
            mid = m.get("id")
            if not mid:
                continue
            try:
                msg = client.get_message(mid)
                triage_item = analyze_email(msg)
                items.append(triage_item)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not process message {mid}: {e}[/yellow]")

    batch = TriageBatch(total_unread=len(items), items=items)

    if as_json:
        console.print(batch.model_dump_json(indent=2))
        return

    # Render rich summary table
    table = Table(title=f"📬 Unread Emails Triage ({len(items)} items)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Category", style="cyan", width=16)
    table.add_column("From & Date", style="magenta", width=26)
    table.add_column("Summary & Subject", style="bold white", width=36)
    table.add_column("Action Items / Dates", style="yellow", width=38)

    for i, item in enumerate(items, 1):
        sender_str = f"{item.sender_name or item.sender_email}\n[dim]{item.date[:16]}[/dim]"
        summary_str = f"[bold]{item.title_summary}[/bold]\n[dim]{item.brief_summary[:120]}...[/dim]"

        actions_and_dates: list[str] = []
        for action in item.action_items[:2]:
            actions_and_dates.append(f"⚡ [bold]{action}[/bold]")
        for event in item.calendar_events[:2]:
            actions_and_dates.append(f"📅 [cyan]{event.summary}[/cyan]")

        act_str = "\n".join(actions_and_dates) if actions_and_dates else "[dim]No explicit actions/dates[/dim]"
        table.add_row(str(i), item.category, sender_str, summary_str, act_str)

    console.print(table)
    console.print(
        "\n[bold]Tip:[/bold] Run [cyan]inbox-zero review[/cyan] to interactively review each email and mark as read or add events."
    )


@app.command()
def review(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum unread emails to review."),
    query: str = typer.Option("is:unread", "--query", "-q", help="Gmail search query."),
) -> None:
    """Interactively review each email, inspect details, add to calendar, and mark as read."""
    client = GWSClient()
    try:
        unread_list = client.list_unread_messages(max_results=limit, query=query)
    except GWSClientError as err:
        console.print(f"[bold red]Failed to fetch unread messages:[/bold red] {err}")
        raise typer.Exit(code=1)

    if not unread_list:
        console.print("[green]🎉 Inbox Zero! No unread messages found.[/green]")
        return

    console.print(f"[bold green]Starting interactive triage for {len(unread_list)} unread messages...[/bold green]\n")

    for i, m in enumerate(unread_list, 1):
        mid = m.get("id")
        if not mid:
            continue

        try:
            msg = client.get_message(mid)
            item = analyze_email(msg)
        except Exception as e:
            console.print(f"[red]Error reading email {mid}: {e}[/red]")
            continue

        # Render panel for item
        body_content = f"""
**From:** {item.sender_name or 'Unknown'} <{item.sender_email}>
**Date:** {item.date}
**Subject:** {item.subject}
**Category:** {item.category}

### 📝 Summary
{item.brief_summary}

### ⚡ Action Items
{chr(10).join(f"- {a}" for a in item.action_items) if item.action_items else "_None detected_"}

### 📅 Calendar Dates / Events
{chr(10).join(f"- **{e.summary}** ({e.start_time})" for e in item.calendar_events) if item.calendar_events else "_None detected_"}
"""
        console.print(
            Panel(
                Markdown(body_content),
                title=f"[{i}/{len(unread_list)}] {item.title_summary}",
                border_style="bright_blue",
            )
        )

        # Prompt user
        choice = typer.prompt(
            "Action: [y] Mark Read, [n] Keep Unread, [c] Add to Calendar, [q] Quit",
            default="y",
        ).strip().lower()

        if choice == "q":
            console.print("[yellow]Triage stopped by user.[/yellow]")
            break
        elif choice == "c" and item.calendar_events:
            for ev in item.calendar_events:
                confirm = typer.confirm(f"Add event '{ev.summary}' ({ev.start_time}) to calendar?", default=True)
                if confirm:
                    try:
                        client.insert_calendar_event(
                            summary=ev.summary,
                            start_time=ev.start_time,
                            description=ev.description or "",
                        )
                        console.print(f"[green]✓ Added to Google Calendar![/green]")
                    except Exception as e:
                        console.print(f"[red]Failed to insert calendar event: {e}[/red]")
            
            mark = typer.confirm("Now mark this email as read?", default=True)
            if mark:
                client.mark_as_read(item.message_id)
                console.print(f"[green]✓ Marked as read.[/green]")
        elif choice in ("y", "yes"):
            if client.mark_as_read(item.message_id):
                console.print(f"[green]✓ Marked as read.[/green]")
            else:
                console.print(f"[red]✗ Failed to mark as read.[/red]")
        else:
            console.print("[dim]Kept unread.[/dim]")

        console.print("=" * 60)


@app.command()
def mark_read(
    message_ids: list[str] = typer.Argument(..., help="List of message IDs to mark as read."),
) -> None:
    """Mark specified email IDs as read."""
    client = GWSClient()
    for mid in message_ids:
        if client.mark_as_read(mid):
            console.print(f"[green]✓ Marked {mid} as read.[/green]")
        else:
            console.print(f"[red]✗ Failed to mark {mid} as read.[/red]")


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
