"""Deterministic Google Workspace CLI (gws) wrapper client."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from inbox_zero.models import EmailAttachment, EmailMessage, Sender
from inbox_zero.parser import (
    decode_base64url,
    extract_attachment_metadata,
    extract_clean_email_body,
    parse_attachment_bytes,
)

logger = logging.getLogger(__name__)


class GWSClientError(Exception):
    """Exception raised for general errors executing gws commands."""
    pass


class GWSAuthError(GWSClientError):
    """Exception raised when gws authentication is missing, invalid, or expired."""
    def __init__(self, message: str = "Google Workspace CLI (gws) is not authenticated. Please run 'gws auth login' to authenticate.") -> None:
        super().__init__(message)


class GWSClient:
    """Wrapper client around gws CLI."""

    def __init__(self, timeout: int = 30, check_auth_on_init: bool = False) -> None:
        self.timeout = timeout
        if check_auth_on_init:
            self.ensure_authenticated()

    def ensure_authenticated(self) -> None:
        """Check authentication status and fail fast if unauthenticated."""
        try:
            status = self._run_cmd(["gws", "auth", "status"], skip_auth_check=True)
            if not isinstance(status, dict) or not status.get("token_valid", False):
                raise GWSAuthError()
        except GWSClientError as err:
            if isinstance(err, GWSAuthError):
                raise
            raise GWSAuthError(f"Google Workspace CLI (gws) authentication check failed: {err}. Please run 'gws auth login'.") from err

    def _run_cmd(self, cmd: list[str], input_data: str | None = None, skip_auth_check: bool = False) -> Any:
        """Run a gws CLI command and parse JSON output."""
        logger.debug("Running command: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise GWSClientError("gws CLI is not installed or not in PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise GWSClientError(f"Command timed out after {self.timeout}s: {' '.join(cmd)}") from exc

        # Check for authentication failure (exit code 2 or auth error text)
        if result.returncode == 2 or any(
            err_keyword in result.stderr.lower() for err_keyword in ["auth error", "credentials missing", "token expired", "unauthenticated", "invalid_grant"]
        ):
            raise GWSAuthError()

        if result.returncode != 0:
            err_msg = result.stderr.strip() or f"Command failed with exit code {result.returncode}"
            logger.error("gws command failed: %s | stderr: %s", " ".join(cmd), err_msg)
            raise GWSClientError(f"gws error: {err_msg}")

        stdout = result.stdout.strip()
        if not stdout:
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode JSON from gws: %s", stdout)
            raise GWSClientError(f"Invalid JSON returned from gws: {stdout[:200]}") from exc

    def list_unread_threads(self, max_results: int = 20, query: str = "is:unread") -> list[dict[str, Any]]:
        """List unread conversation threads using gws gmail users threads list."""
        cmd = [
            "gws",
            "gmail",
            "users",
            "threads",
            "list",
            "--params",
            json.dumps({"userId": "me", "q": query, "maxResults": max_results}),
            "--format",
            "json",
        ]
        data = self._run_cmd(cmd)
        if isinstance(data, dict):
            return data.get("threads", [])
        if isinstance(data, list):
            return data
        return []

    def list_unread_messages(self, max_results: int = 20, query: str = "is:unread") -> list[dict[str, Any]]:
        """List unread messages using gws gmail +triage."""
        cmd = [
            "gws",
            "gmail",
            "+triage",
            "--max",
            str(max_results),
            "--query",
            query,
            "--format",
            "json",
        ]
        data = self._run_cmd(cmd)
        if isinstance(data, dict):
            return data.get("messages", [])
        if isinstance(data, list):
            return data
        return []

    def get_attachment_bytes(self, message_id: str, attachment_id: str) -> bytes:
        """Fetch raw attachment bytes by attachment ID using gws."""
        cmd = [
            "gws",
            "gmail",
            "users",
            "messages",
            "attachments",
            "get",
            "--params",
            json.dumps({"userId": "me", "messageId": message_id, "id": attachment_id}),
            "--format",
            "json",
        ]
        try:
            raw = self._run_cmd(cmd)
            if isinstance(raw, dict) and "data" in raw:
                return decode_base64url(raw["data"])
        except Exception as e:
            logger.debug("Could not fetch attachment %s for message %s: %s", attachment_id, message_id, e)
        return b""

    def get_message(self, message_id: str, fetch_attachments: bool = True) -> EmailMessage:
        """Read a message and return parsed EmailMessage with attachments."""
        cmd = [
            "gws",
            "gmail",
            "+read",
            "--id",
            message_id,
            "--headers",
            "--format",
            "json",
        ]
        raw = self._run_cmd(cmd)
        if not isinstance(raw, dict):
            raise GWSClientError(f"Unexpected response fetching message {message_id}: {raw}")

        sender = Sender.from_gws(raw.get("from"))
        body_text = raw.get("body_text") or ""
        body_html = raw.get("body_html")
        cleaned_body = extract_clean_email_body(body_text, body_html)

        attachments: list[EmailAttachment] = []
        if fetch_attachments:
            try:
                # Inspect message payload to discover any attachments
                msg_cmd = [
                    "gws",
                    "gmail",
                    "users",
                    "messages",
                    "get",
                    "--params",
                    json.dumps({"userId": "me", "id": message_id, "format": "full"}),
                    "--format",
                    "json",
                ]
                msg_raw = self._run_cmd(msg_cmd)
                if isinstance(msg_raw, dict) and "payload" in msg_raw:
                    meta_list = extract_attachment_metadata(msg_raw["payload"])
                    for meta in meta_list:
                        att_bytes = b""
                        if meta.get("inline_data"):
                            att_bytes = decode_base64url(meta["inline_data"])
                        elif meta.get("id"):
                            att_bytes = self.get_attachment_bytes(message_id, meta["id"])

                        extracted_text = ""
                        if att_bytes:
                            extracted_text = parse_attachment_bytes(
                                att_bytes, meta["filename"], meta.get("mime_type", "")
                            )

                        attachments.append(
                            EmailAttachment(
                                id=meta.get("id"),
                                filename=meta["filename"],
                                mime_type=meta.get("mime_type", "application/octet-stream"),
                                size_bytes=meta.get("size_bytes", len(att_bytes)),
                                extracted_text=extracted_text,
                            )
                        )
            except Exception as e:
                logger.debug("Could not inspect attachments for message %s: %s", message_id, e)

        return EmailMessage(
            id=message_id,
            thread_id=raw.get("thread_id") or message_id,
            subject=raw.get("subject") or "(No Subject)",
            sender=sender,
            date=raw.get("date") or "",
            body_text=cleaned_body,
            body_html=body_html,
            snippet=raw.get("snippet"),
            is_unread=True,
            attachments=attachments,
        )

    def get_thread(self, thread_id: str) -> list[EmailMessage]:
        """Fetch all messages belonging to a conversation thread in chronological order."""
        cmd = [
            "gws",
            "gmail",
            "users",
            "threads",
            "get",
            "--params",
            json.dumps({"userId": "me", "id": thread_id}),
            "--format",
            "json",
        ]
        raw = self._run_cmd(cmd)
        if not isinstance(raw, dict):
            raise GWSClientError(f"Unexpected response fetching thread {thread_id}: {raw}")

        messages_raw = raw.get("messages", [])
        if not messages_raw:
            # Fallback: fetch individual message if thread messages are empty
            try:
                msg = self.get_message(thread_id)
                return [msg]
            except Exception:
                return []

        messages: list[EmailMessage] = []
        for m in messages_raw:
            mid = m.get("id")
            if not mid:
                continue
            try:
                email_msg = self.get_message(mid)
                email_msg.is_unread = "UNREAD" in m.get("labelIds", [])
                email_msg.thread_id = thread_id
                messages.append(email_msg)
            except Exception as exc:
                logger.warning("Could not fetch message %s in thread %s: %s", mid, thread_id, exc)

        return messages

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read by removing the UNREAD label."""
        cmd = [
            "gws",
            "gmail",
            "users",
            "messages",
            "modify",
            "--params",
            json.dumps({"userId": "me", "id": message_id}),
            "--json",
            json.dumps({"removeLabelIds": ["UNREAD"]}),
        ]
        try:
            res = self._run_cmd(cmd)
            return bool(res and "id" in res)
        except GWSAuthError:
            raise
        except Exception as e:
            logger.error("Failed to mark message %s as read: %s", message_id, e)
            return False

    def mark_thread_as_read(self, thread_id: str) -> bool:
        """Mark an entire conversation thread as read by removing the UNREAD label."""
        cmd = [
            "gws",
            "gmail",
            "users",
            "threads",
            "modify",
            "--params",
            json.dumps({"userId": "me", "id": thread_id}),
            "--json",
            json.dumps({"removeLabelIds": ["UNREAD"]}),
        ]
        try:
            res = self._run_cmd(cmd)
            return bool(res and "id" in res)
        except GWSAuthError:
            raise
        except Exception as e:
            logger.error("Failed to mark thread %s as read: %s", thread_id, e)
            return False

    def mark_multiple_as_read(self, message_ids: list[str]) -> dict[str, bool]:
        """Mark multiple messages as read."""
        results: dict[str, bool] = {}
        for mid in message_ids:
            results[mid] = self.mark_as_read(mid)
        return results

    def send_reply(self, message_id: str, body: str, reply_all: bool = False) -> bool:
        """Reply to an email message using gws."""
        cmd = [
            "gws",
            "gmail",
            "+reply-all" if reply_all else "+reply",
            "--message-id",
            message_id,
            "--body",
            body,
        ]
        try:
            self._run_cmd(cmd)
            return True
        except GWSAuthError:
            raise
        except Exception as e:
            logger.error("Failed to send reply to %s: %s", message_id, e)
            return False

    def insert_calendar_event(
        self,
        summary: str,
        start_time: str,
        end_time: str | None = None,
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Insert an event into Google Calendar."""
        cmd = [
            "gws",
            "calendar",
            "+insert",
            "--summary",
            summary,
            "--start",
            start_time,
        ]
        if end_time:
            cmd.extend(["--end", end_time])
        if description:
            cmd.extend(["--description", description])
        if location:
            cmd.extend(["--location", location])

        res = self._run_cmd(cmd)
        if isinstance(res, dict):
            return res
        return {"status": "ok", "raw": res}
