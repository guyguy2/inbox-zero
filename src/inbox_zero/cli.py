"""Interactive Command-Line Interface for inbox-zero using Typer and Rich."""

from __future__ import annotations

import json
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from inbox_zero.analyzer import analyze_email
from inbox_zero.client import GWSClient, GWSClientError, GWSAuthError
from inbox_zero.models import TriageBatch, TriageItem

app = typer.Typer(
    name="inbox-zero",
    help="AI & Deterministic Email Triage, Action Items, Replies & Calendar Manager using gws.",
    add_completion=False,
)
console = Console()


def _handle_gws_error(err: Exception) -> None:
    """Pretty-print gws errors and fail fast."""
    if isinstance(err, GWSAuthError):
        console.print(
            "\n[bold red]❌ Authentication Required:[/bold red] Google Workspace CLI (`gws`) is not authenticated.\n"
            "👉 Please run: [bold cyan]gws auth login[/bold cyan] to authenticate and then rerun this command.\n"
        )
    else:
        console.print(f"\n[bold red]❌ Error executing gws command:[/bold red] {err}\n")
    raise typer.Exit(code=2 if isinstance(err, GWSAuthError) else 1)


@app.command()
def scan(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum unread emails to scan."),
    query: str = typer.Option("is:unread", "--query", "-q", help="Gmail search filter query."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON for AI agents/scripts."),
) -> None:
    """Scan unread emails, extract summaries, action items, dates, and suggested replies."""
    client = GWSClient()
    try:
        client.ensure_authenticated()
        if not as_json:
            with console.status("[bold green]Scanning unread emails via gws...[/bold green]"):
                unread_list = client.list_unread_messages(max_results=limit, query=query)
        else:
            unread_list = client.list_unread_messages(max_results=limit, query=query)
    except GWSClientError as err:
        _handle_gws_error(err)

    if not unread_list:
        if as_json:
            print(TriageBatch(total_unread=0, items=[]).model_dump_json(indent=2))
        else:
            console.print("[green]🎉 Inbox Zero! No unread messages found matching query.[/green]")
        return

    items: list[TriageItem] = []
    if not as_json:
        with console.status(f"[bold blue]Analyzing {len(unread_list)} emails...[/bold blue]"):
            for m in unread_list:
                mid = m.get("id")
                if not mid:
                    continue
                try:
                    msg = client.get_message(mid)
                    triage_item = analyze_email(msg)
                    items.append(triage_item)
                except GWSAuthError as err:
                    _handle_gws_error(err)
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not process message {mid}: {e}[/yellow]")
    else:
        for m in unread_list:
            mid = m.get("id")
            if not mid:
                continue
            try:
                msg = client.get_message(mid)
                triage_item = analyze_email(msg)
                items.append(triage_item)
            except GWSAuthError as err:
                _handle_gws_error(err)
            except Exception:
                continue

    batch = TriageBatch(total_unread=len(items), items=items)

    if as_json:
        # Use standard print to prevent rich console word wrapping in JSON output
        print(batch.model_dump_json(indent=2))
        return

    # Render rich summary table
    table = Table(title=f"📬 Unread Emails Triage ({len(items)} items)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Category", style="cyan", width=16)
    table.add_column("From & Date", style="magenta", width=26)
    table.add_column("Summary & Subject", style="bold white", width=34)
    table.add_column("Action Items / Dates / Replies", style="yellow", width=40)

    for i, item in enumerate(items, 1):
        sender_str = f"{item.sender_name or item.sender_email}\n[dim]{item.date[:16]}[/dim]"
        summary_str = f"[bold]{item.title_summary}[/bold]\n[dim]{item.brief_summary[:120]}...[/dim]"

        details: list[str] = []
        for action in item.action_items[:2]:
            details.append(f"⚡ [bold]{action}[/bold]")
        for event in item.calendar_events[:2]:
            details.append(f"📅 [cyan]{event.summary}[/cyan]")
        if item.suggested_replies:
            details.append(f"💬 [green]Reply: \"{item.suggested_replies[0][:50]}...\"[/green]")

        details_str = "\n".join(details) if details else "[dim]No explicit actions/dates[/dim]"
        table.add_row(str(i), item.category, sender_str, summary_str, details_str)

    console.print(table)
    console.print(
        "\n[bold]Tip:[/bold] Run [cyan]inbox-zero review[/cyan] to interactively review, reply, add events, and mark emails as read."
    )


@app.command()
def review(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum unread emails to review."),
    query: str = typer.Option("is:unread", "--query", "-q", help="Gmail search query."),
) -> None:
    """Interactively review each email, reply, add to calendar, and mark as read."""
    client = GWSClient()
    try:
        client.ensure_authenticated()
        unread_list = client.list_unread_messages(max_results=limit, query=query)
    except GWSClientError as err:
        _handle_gws_error(err)

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
        except GWSAuthError as err:
            _handle_gws_error(err)
        except Exception as e:
            console.print(f"[red]Error reading email {mid}: {e}[/red]")
            continue

        # Format suggested replies
        replies_md = (
            "\n".join(f"- *\"{r}\"*" for r in item.suggested_replies)
            if item.suggested_replies
            else "_No reply needed (automated or acknowledged)_"
        )

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

### 💬 Suggested Replies
{replies_md}
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
            "Action: [y] Mark Read, [n] Keep Unread, [c] Add to Calendar, [r] Send Reply, [q] Quit",
            default="y",
        ).strip().lower()

        if choice == "q":
            console.print("[yellow]Triage stopped by user.[/yellow]")
            break
        elif choice == "r":
            reply_text = ""
            if item.suggested_replies:
                console.print("\n[bold]Choose a suggested reply or enter custom text:[/bold]")
                for idx, r in enumerate(item.suggested_replies, 1):
                    console.print(f"  [{idx}] {r}")
                console.print("  [c] Custom reply")
                console.print("  [s] Skip reply")
                sub_choice = typer.prompt("Select reply option", default="1").strip()
                if sub_choice.isdigit() and 1 <= int(sub_choice) <= len(item.suggested_replies):
                    reply_text = item.suggested_replies[int(sub_choice) - 1]
                elif sub_choice.lower() == "c":
                    reply_text = typer.prompt("Enter reply text")

            if reply_text:
                try:
                    if client.send_reply(item.message_id, reply_text):
                        console.print(f"[green]✓ Reply sent![/green]")
                        mark = typer.confirm("Mark as read now?", default=True)
                        if mark:
                            client.mark_as_read(item.message_id)
                            console.print(f"[green]✓ Marked as read.[/green]")
                    else:
                        console.print(f"[red]✗ Failed to send reply.[/red]")
                except Exception as e:
                    console.print(f"[red]Error sending reply: {e}[/red]")
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
    try:
        client.ensure_authenticated()
    except GWSClientError as err:
        _handle_gws_error(err)

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
