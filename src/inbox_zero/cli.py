"""Interactive Command-Line Interface for inbox-zero using Typer and Rich."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from inbox_zero.agent_bridge import (
    AgentExecutionError,
    apply_agent_decisions,
    build_agent_prompt,
    prepare_agent_triage_payload,
    run_agent,
)
from inbox_zero.analyzer import analyze_email, analyze_thread
from inbox_zero.client import GWSClient, GWSClientError, GWSAuthError
from inbox_zero.config import load_config
from inbox_zero.keys import get_single_key
from inbox_zero.models import EmailMessage, TriageBatch, TriageItem

app = typer.Typer(
    name="inbox-zero",
    help="AI & Deterministic Email Triage, Action Items, Replies & Calendar Manager using gws.",
    add_completion=False,
    no_args_is_help=True,
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
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Maximum unread threads to scan."),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Gmail search filter query."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON for AI agents/scripts."),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom configuration file (TOML or JSON).",
    ),
) -> None:
    """Scan unread email threads, extract summaries, action items, dates, and suggested replies."""
    cfg = load_config(config_file)
    actual_limit = limit if limit is not None else cfg.default_limit
    actual_query = query if query is not None else cfg.default_query

    client = GWSClient()
    try:
        client.ensure_authenticated()
        if not as_json:
            with console.status("[bold green]Scanning unread threads via gws...[/bold green]"):
                threads_list = client.list_unread_threads(max_results=actual_limit, query=actual_query)
        else:
            threads_list = client.list_unread_threads(max_results=actual_limit, query=actual_query)
    except GWSClientError as err:
        _handle_gws_error(err)

    if not threads_list:
        if as_json:
            print(TriageBatch(total_unread=0, total_messages=0, items=[]).model_dump_json(indent=2))
        else:
            console.print("[green]🎉 Inbox Zero! No unread messages found matching query.[/green]")
        return

    items: list[TriageItem] = []
    total_messages = 0

    if not as_json:
        with console.status(f"[bold blue]Analyzing {len(threads_list)} email threads...[/bold blue]"):
            for t in threads_list:
                tid = t.get("id")
                if not tid:
                    continue
                try:
                    messages = client.get_thread(tid)
                    if not messages:
                        continue
                    item = analyze_thread(messages)
                    items.append(item)
                    total_messages += len(messages)
                except GWSAuthError as err:
                    _handle_gws_error(err)
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not process thread {tid}: {e}[/yellow]")
    else:
        for t in threads_list:
            tid = t.get("id")
            if not tid:
                continue
            try:
                messages = client.get_thread(tid)
                if not messages:
                    continue
                item = analyze_thread(messages)
                items.append(item)
                total_messages += len(messages)
            except GWSAuthError as err:
                _handle_gws_error(err)
            except Exception:
                continue

    if not items:
        if as_json:
            print(TriageBatch(total_unread=0, total_messages=0, items=[]).model_dump_json(indent=2))
        else:
            console.print("[green]🎉 Inbox Zero! No unread messages found matching query.[/green]")
        return

    batch = TriageBatch(total_unread=len(items), total_messages=total_messages, items=items)

    if as_json:
        # Use standard print to prevent rich console word wrapping in JSON output
        print(batch.model_dump_json(indent=2))
        return

    # Render rich summary table
    chunk_size = 10
    total_items = len(items)

    if total_items <= chunk_size:
        table_title = (
            f"📬 Unread Emails Triage ({total_items} threads / {total_messages} messages)"
            if total_messages > total_items
            else f"📬 Unread Emails Triage ({total_items} items)"
        )
        table = Table(title=table_title, show_lines=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Category", style="cyan", width=16)
        table.add_column("From & Date", style="magenta", width=26)
        table.add_column("Summary & Subject", style="bold white", width=34)
        table.add_column("Action Items / Dates / Replies", style="yellow", width=40)

        for i, item in enumerate(items, 1):
            if len(item.senders) > 1:
                senders_str = ", ".join(s.name or s.email.split("@")[0] for s in item.senders)
                sender_display = f"[bold]{senders_str}[/bold] [cyan]({item.message_count} msgs)[/cyan]\n[dim]{item.date[:16]}[/dim]"
            else:
                sender_display = f"{item.sender_name or item.sender_email}\n[dim]{item.date[:16]}[/dim]"

            summary_str = f"[bold]{item.title_summary}[/bold]\n[dim]{item.brief_summary[:120]}...[/dim]"

            details: list[str] = []
            for action in item.action_items[:2]:
                details.append(f"⚡ [bold]{action}[/bold]")
            for event in item.calendar_events[:2]:
                details.append(f"📅 [cyan]{event.summary}[/cyan]")
            if item.suggested_replies:
                details.append(f"💬 [green]Reply: \"{item.suggested_replies[0][:50]}...\"[/green]")

            details_str = "\n".join(details) if details else "[dim]No explicit actions/dates[/dim]"
            table.add_row(str(i), item.category, sender_display, summary_str, details_str)

        console.print(table)
    else:
        num_pages = (total_items + chunk_size - 1) // chunk_size
        for page_idx in range(num_pages):
            start_idx = page_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_items)
            page_items = items[start_idx:end_idx]

            table_title = (
                f"📬 Unread Emails Triage — Page {page_idx + 1}/{num_pages} (Items {start_idx + 1}–{end_idx} of {total_items})"
            )
            table = Table(title=table_title, show_lines=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Category", style="cyan", width=16)
            table.add_column("From & Date", style="magenta", width=26)
            table.add_column("Summary & Subject", style="bold white", width=34)
            table.add_column("Action Items / Dates / Replies", style="yellow", width=40)

            for i, item in enumerate(page_items, start_idx + 1):
                if len(item.senders) > 1:
                    senders_str = ", ".join(s.name or s.email.split("@")[0] for s in item.senders)
                    sender_display = f"[bold]{senders_str}[/bold] [cyan]({item.message_count} msgs)[/cyan]\n[dim]{item.date[:16]}[/dim]"
                else:
                    sender_display = f"{item.sender_name or item.sender_email}\n[dim]{item.date[:16]}[/dim]"

                summary_str = f"[bold]{item.title_summary}[/bold]\n[dim]{item.brief_summary[:120]}...[/dim]"

                details: list[str] = []
                for action in item.action_items[:2]:
                    details.append(f"⚡ [bold]{action}[/bold]")
                for event in item.calendar_events[:2]:
                    details.append(f"📅 [cyan]{event.summary}[/cyan]")
                if item.suggested_replies:
                    details.append(f"💬 [green]Reply: \"{item.suggested_replies[0][:50]}...\"[/green]")

                details_str = "\n".join(details) if details else "[dim]No explicit actions/dates[/dim]"
                table.add_row(str(i), item.category, sender_display, summary_str, details_str)

            console.print(table)

            if page_idx < num_pages - 1:
                if sys.stdin.isatty():
                    console.print(
                        f"\n[bold cyan]Showing page {page_idx + 1} of {num_pages} ({end_idx}/{total_items} items). Press [⏎ / →] for next page, [q / Esc] to exit: [/bold cyan]",
                        end="",
                    )
                    nav_key = get_single_key().strip().lower()
                    console.print()
                    if nav_key in ("q", "quit", "exit", "esc"):
                        console.print("[yellow]Scan stopped by user.[/yellow]")
                        break
                else:
                    console.print()

    console.print(
        "\n[bold]Tip:[/bold] Run [cyan]inbox-zero review[/cyan] to interactively review full conversation threads, reply, add events, and mark as read."
    )


@app.command()
def review(
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Maximum unread threads to review."),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Gmail search query."),
    show_body: Optional[bool] = typer.Option(
        None,
        "--show-body/--no-show-body",
        help="Show full email thread body in review mode (overrides config).",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom configuration file (TOML or JSON).",
    ),
) -> None:
    """Interactively review each email thread, inspect overview, reply, add to calendar, and mark as read."""
    cfg = load_config(config_file)
    actual_limit = limit if limit is not None else cfg.default_limit
    actual_query = query if query is not None else cfg.default_query
    display_body = show_body if show_body is not None else cfg.review.show_body

    client = GWSClient()
    try:
        client.ensure_authenticated()
        threads_list = client.list_unread_threads(max_results=actual_limit, query=actual_query)
    except GWSClientError as err:
        _handle_gws_error(err)

    if not threads_list:
        console.print("[green]🎉 Inbox Zero! No unread messages found.[/green]")
        return

    total_threads = len(threads_list)
    total_batches = (total_threads + 9) // 10

    if total_threads > 10:
        console.print(
            f"[bold green]Starting interactive triage for {total_threads} unread conversation threads ({total_batches} batches of 10)...[/bold green]\n"
        )
    else:
        console.print(
            f"[bold green]Starting interactive triage for {total_threads} unread conversation threads...[/bold green]\n"
        )

    idx = 0
    prev_idx = -1
    user_quits = False
    try:
        while idx < total_threads:
            # If we crossed a 10-item batch boundary while moving forward
            if total_threads > 10 and idx > 0 and idx % 10 == 0 and prev_idx < idx:
                completed_batch = idx // 10
                next_batch = completed_batch + 1
                next_end = min(idx + 10, total_threads)
                console.print(
                    Panel(
                        f"🎉 [bold green]Batch {completed_batch} of {total_batches} Complete![/bold green] "
                        f"({idx} of {total_threads} threads reviewed)\n\n"
                        f"• Press [bold green][⏎ / →][/bold green] to continue to [bold cyan]Batch {next_batch}[/bold cyan] (threads {idx + 1}–{next_end})\n"
                        f"• Press [bold yellow][↑ / p][/bold yellow] to go back to previous thread\n"
                        f"• Press [bold dim][q / Esc][/bold dim] to stop triage",
                        title=f"📦 Batch {completed_batch}/{total_batches} Milestone",
                        border_style="green",
                    )
                )
                console.print(
                    f"[bold cyan]Continue to Batch {next_batch}? [⏎ / →] Next Batch  [↑ / p] Go Back  [q] Quit: [/bold cyan]",
                    end="",
                )
                batch_key = get_single_key().strip().lower()
                console.print()
                if batch_key in ("q", "quit", "exit", "esc"):
                    console.print("[yellow]Triage stopped by user.[/yellow]")
                    user_quits = True
                    break
                elif batch_key in ("up", "p", "prev", "previous"):
                    idx -= 1
                    prev_idx = idx
                    continue

            prev_idx = idx
            t = threads_list[idx]
            tid = t.get("id")
            if not tid:
                idx += 1
                continue

            try:
                messages = client.get_thread(tid)
                if not messages:
                    idx += 1
                    continue
                item = analyze_thread(messages)
            except GWSAuthError as err:
                _handle_gws_error(err)
            except Exception as e:
                console.print(f"[red]Error reading thread {tid}: {e}[/red]")
                idx += 1
                continue

            # Format thread participants
            participants_str = ", ".join(f"{s.name or 'Unknown'} <{s.email}>" for s in item.senders)

            # Build thread messages section
            thread_messages_md: list[str] = []
            for msg_idx, msg in enumerate(item.messages, 1):
                unread_badge = " *(UNREAD)*" if msg.is_unread else ""
                msg_body = msg.body_text.strip() or "_No text content_"
                thread_messages_md.append(
                    f"#### 💬 [{msg_idx}/{len(item.messages)}] From {msg.sender.name or 'Unknown'} `<{msg.sender.email}>` ({msg.date}){unread_badge}\n\n{msg_body}"
                )

            messages_block = "\n\n---\n\n".join(thread_messages_md)

            # Format suggested replies
            replies_md = (
                "\n".join(f"- *\"{r}\"*" for r in item.suggested_replies)
                if item.suggested_replies
                else "_No reply needed (automated or acknowledged)_"
            )

            thread_section = f"\n---\n### 🧵 Conversation Thread\n\n{messages_block}\n" if display_body else ""

            body_content = f"""
**Participants:** {participants_str}
**Category:** {item.category} | **Thread Size:** {item.message_count} message(s) ({item.unread_count} unread)
{thread_section}
---
### 📝 Overview
{item.brief_summary}

### ⚡ Action Items
{chr(10).join(f"- {a}" for a in item.action_items) if item.action_items else "_None detected_"}

### 📅 Calendar Dates / Events
{chr(10).join(f"- **{e.summary}** ({e.start_time})" for e in item.calendar_events) if item.calendar_events else "_None detected_"}

### 💬 Suggested Replies (Reply to Thread)
{replies_md}
"""
            batch_num = (idx // 10) + 1
            panel_title = (
                f"[{idx + 1}/{total_threads}] (Batch {batch_num}/{total_batches}) {item.title_summary}"
                if total_threads > 10
                else f"[{idx + 1}/{total_threads}] {item.title_summary}"
            )
            console.print(
                Panel(
                    Markdown(body_content),
                    title=panel_title,
                    border_style="bright_blue",
                )
            )

            prompt_text = (
                "[bold cyan]Action:[/bold cyan] [bold green]\\[⏎ / →] Mark Read[/bold green], [yellow]\\[← / s] Keep Unread[/yellow], [blue]\\[↓ / v] View Full Email[/blue], [magenta]\\[r] Send Reply[/magenta], [cyan]\\[c] Add to Calendar[/cyan], [dim]\\[q] Quit[/dim]: "
                if not display_body
                else "[bold cyan]Action:[/bold cyan] [bold green]\\[⏎ / →] Mark Read[/bold green], [yellow]\\[← / s] Keep Unread[/yellow], [magenta]\\[r] Send Reply[/magenta], [cyan]\\[c] Add to Calendar[/cyan], [dim]\\[q] Quit[/dim]: "
            )

            while True:
                console.print(prompt_text, end="")
                choice = get_single_key().strip().lower()
                console.print()

                if choice in ("q", "quit", "exit", "esc"):
                    console.print("[yellow]Triage stopped by user.[/yellow]")
                    user_quits = True
                    break

                if choice in ("?", "h", "help"):
                    console.print(
                        Panel(
                            "  • [bold green][⏎][/bold green] or [bold green][→][/bold green] or [bold green][d][/bold green] : Mark thread as read & advance to next\n"
                            "  • [yellow][←][/yellow] or [yellow][s][/yellow] or [yellow][n][/yellow]     : Keep thread unread (skip) & advance to next\n"
                            "  • [cyan][↑][/cyan] or [cyan][p][/cyan]             : Go back to previous email thread\n"
                            "  • [blue][↓][/blue] or [blue][v][/blue]             : View full conversation thread / email body\n"
                            "  • [magenta][r][/magenta]                   : Send a suggested or custom reply\n"
                            "  • [cyan][c][/cyan]                   : Add detected date/meeting to Google Calendar\n"
                            "  • [dim][q][/dim] or [dim][Esc][/dim]          : Quit interactive review",
                            title="⌨️  Keyboard Shortcuts",
                            border_style="cyan",
                        )
                    )
                    continue

                if choice in ("up", "p", "prev", "previous"):
                    if idx > 0:
                        idx -= 1
                        break
                    else:
                        console.print("[yellow]Already at the first email thread.[/yellow]")
                        continue

                if choice in ("v", "view", "body", "down", "o"):
                    console.print(
                        Panel(
                            Markdown(f"### 🧵 Conversation Thread\n\n{messages_block}"),
                            title=f"Full Thread: {item.title_summary}",
                            border_style="cyan",
                        )
                    )
                    continue

                if choice in ("r", "reply"):
                    reply_text = ""
                    if item.suggested_replies:
                        console.print("\n[bold]Choose a suggested reply or enter custom text:[/bold]")
                        for r_idx, r in enumerate(item.suggested_replies, 1):
                            console.print(f"  [{r_idx}] {r}")
                        console.print("  [c] Custom reply")
                        console.print("  [s / Esc] Skip reply")
                        
                        console.print("Select reply option [1]: ", end="")
                        sub_choice = get_single_key().strip().lower()
                        console.print()

                        if sub_choice in ("enter", "1", "") and len(item.suggested_replies) >= 1:
                            reply_text = item.suggested_replies[0]
                        elif sub_choice.isdigit() and 1 <= int(sub_choice) <= len(item.suggested_replies):
                            reply_text = item.suggested_replies[int(sub_choice) - 1]
                        elif sub_choice in ("c", "custom"):
                            reply_text = typer.prompt("Enter reply text")
                        elif sub_choice in ("s", "esc", "q"):
                            console.print("[dim]Reply cancelled.[/dim]")
                            continue
                    else:
                        reply_text = typer.prompt("Enter reply text")

                    if reply_text:
                        try:
                            if client.send_reply(item.message_id, reply_text):
                                console.print(f"[green]✓ Reply sent to thread![/green]")
                                console.print("[bold]Mark entire thread as read now? [⏎ / y] Yes  [n] No:[/bold] ", end="")
                                mark_confirm = get_single_key().strip().lower()
                                console.print()
                                if mark_confirm in ("enter", "y", "yes", "d", "right", ""):
                                    client.mark_thread_as_read(item.thread_id)
                                    console.print(f"[green]✓ Thread marked as read.[/green]")
                            else:
                                console.print(f"[red]✗ Failed to send reply.[/red]")
                        except Exception as e:
                            console.print(f"[red]Error sending reply: {e}[/red]")
                    idx += 1
                    break

                if choice in ("c", "cal", "calendar"):
                    if not item.calendar_events:
                        console.print("[yellow]No calendar dates/events detected in this thread.[/yellow]")
                        continue

                    for ev in item.calendar_events:
                        console.print(f"Add event '[bold cyan]{ev.summary}[/bold cyan]' ({ev.start_time}) to calendar? [⏎ / y] Yes  [n] Skip: ", end="")
                        ev_confirm = get_single_key().strip().lower()
                        console.print()
                        if ev_confirm in ("enter", "y", "yes", "d", "right", ""):
                            try:
                                client.insert_calendar_event(
                                    summary=ev.summary,
                                    start_time=ev.start_time,
                                    description=ev.description or "",
                                )
                                console.print(f"[green]✓ Added to Google Calendar![/green]")
                            except Exception as e:
                                console.print(f"[red]Failed to insert calendar event: {e}[/red]")
                        else:
                            console.print("[dim]Skipped adding event.[/dim]")

                    console.print("[bold]Now mark this thread as read? [⏎ / y] Yes  [n] No:[/bold] ", end="")
                    mark_confirm = get_single_key().strip().lower()
                    console.print()
                    if mark_confirm in ("enter", "y", "yes", "d", "right", ""):
                        client.mark_thread_as_read(item.thread_id)
                        console.print(f"[green]✓ Thread marked as read.[/green]")
                    idx += 1
                    break

                if choice in ("enter", "right", "d", "y", "yes", "e", "read", ""):
                    if client.mark_thread_as_read(item.thread_id):
                        console.print(f"[green]✓ Marked thread as read.[/green]")
                    else:
                        console.print(f"[red]✗ Failed to mark thread as read.[/red]")
                    idx += 1
                    break

                if choice in ("left", "s", "n", "no", "k", "skip", "keep"):
                    console.print("[dim]Kept thread unread.[/dim]")
                    idx += 1
                    break

                console.print(f"[yellow]Unknown option '{choice}'. Press [?] for shortcut help.[/yellow]")

            if user_quits:
                break

            console.print("=" * 60)

        if not user_quits and idx >= total_threads:
            console.print(f"\n[bold green]🎉 All {total_threads} unread email threads reviewed![/bold green]\n")
    except KeyboardInterrupt:
        console.print("\n[yellow]Triage stopped by user.[/yellow]")


@app.command()
def agent(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="AI Agent provider to use ('agy', 'claude', 'codex', 'grok', 'custom'). Defaults to config.",
    ),
    command: Optional[str] = typer.Option(
        None,
        "--command",
        help="Custom CLI command override to execute local subscription agent.",
    ),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Maximum unread threads to triage."),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Gmail search query."),
    auto_apply: bool = typer.Option(False, "--yes", "-y", help="Auto-apply agent decisions without confirmation."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Output generated agent prompt payload without running agent."),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to custom config file."),
) -> None:
    """Triage inbox using a pluggable local AI agent (AGY, Claude Code, Codex, Grok, or custom subscription agent)."""
    cfg = load_config(config_file)
    actual_limit = limit if limit is not None else cfg.default_limit
    actual_query = query if query is not None else cfg.default_query
    actual_provider = provider if provider is not None else cfg.agent.provider
    actual_command = command if command is not None else cfg.agent.command
    should_auto_apply = auto_apply or cfg.agent.auto_apply

    client = GWSClient()
    try:
        client.ensure_authenticated()
    except GWSClientError as err:
        _handle_gws_error(err)

    if not dry_run:
        console.print(f"[bold green]Scanning unread emails for agent triage (Provider: {actual_provider})...[/bold green]")

    try:
        payload = prepare_agent_triage_payload(limit=actual_limit, query=actual_query, client=client)
    except Exception as e:
        console.print(f"[bold red]❌ Error fetching triage payload:[/bold red] {e}")
        raise typer.Exit(1)

    if payload.get("total_unread", 0) == 0:
        console.print("[green]🎉 Inbox Zero! No unread emails to triage.[/green]")
        return

    if dry_run:
        prompt_str = build_agent_prompt(payload, system_prompt=cfg.agent.system_prompt)
        print(prompt_str)
        return

    with console.status(f"[bold blue]Running {actual_provider} agent ({payload['total_unread']} threads)...[/bold blue]"):
        try:
            decisions = run_agent(
                payload,
                provider=actual_provider,
                custom_command=actual_command,
                system_prompt=cfg.agent.system_prompt,
            )
        except AgentExecutionError as e:
            console.print(f"\n[bold red]❌ Agent execution failed:[/bold red] {e}\n")
            raise typer.Exit(1)

    # Display proposed agent decisions
    console.print("\n[bold cyan]🤖 AI Agent Proposed Decisions:[/bold cyan]")
    if "reasoning" in decisions and decisions["reasoning"]:
        console.print(Panel(decisions["reasoning"], title="Agent Reasoning", border_style="dim"))

    replies = decisions.get("replies", [])
    events = decisions.get("calendar_events", [])
    marked_read = decisions.get("mark_as_read", [])

    if replies:
        console.print(f"\n[bold]💬 Suggested Replies ({len(replies)}):[/bold]")
        for r in replies:
            console.print(f"  • Message [cyan]{r.get('message_id')}[/cyan]: \"[green]{r.get('body')}[/green]\"")

    if events:
        console.print(f"\n[bold]📅 Calendar Events ({len(events)}):[/bold]")
        for ev in events:
            console.print(f"  • [cyan]{ev.get('summary')}[/cyan] at [yellow]{ev.get('start_time')}[/yellow]")

    if marked_read:
        console.print(f"\n[bold]✉️  Mark as Read ({len(marked_read)} items):[/bold]")
        for m in marked_read:
            console.print(f"  • [dim]{m}[/dim]")

    if not replies and not events and not marked_read:
        console.print("[yellow]No actionable decisions returned by agent.[/yellow]")
        return

    if not should_auto_apply:
        confirm = typer.confirm("\nApply these agent decisions?", default=True)
        if not confirm:
            console.print("[yellow]Decisions aborted by user.[/yellow]")
            return

    with console.status("[bold green]Applying agent decisions...[/bold green]"):
        results = apply_agent_decisions(decisions, client=client)

    console.print("\n[bold green]✅ Execution Complete:[/bold green]")
    if results.get("replies_sent"):
        console.print(f"  ✓ Replies Sent: {sum(1 for v in results['replies_sent'].values() if v)}")
    if results.get("events_created"):
        console.print(f"  ✓ Calendar Events Added: {len(results['events_created'])}")
    if results.get("marked_read"):
        console.print(f"  ✓ Marked as Read: {sum(1 for v in results['marked_read'].values() if v)}")


@app.command()
def mark_read(
    ids: list[str] = typer.Argument(..., help="List of message IDs or thread IDs to mark as read."),
) -> None:
    """Mark specified thread IDs or email IDs as read."""
    client = GWSClient()
    try:
        client.ensure_authenticated()
    except GWSClientError as err:
        _handle_gws_error(err)

    for target_id in ids:
        if client.mark_thread_as_read(target_id) or client.mark_as_read(target_id):
            console.print(f"[green]✓ Marked {target_id} as read.[/green]")
        else:
            console.print(f"[red]✗ Failed to mark {target_id} as read.[/red]")


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
