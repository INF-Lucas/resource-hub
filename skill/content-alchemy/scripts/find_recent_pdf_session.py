#!/usr/bin/env python3
"""Find the most recent persistent PDF reading session."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from session_paths import list_session_states, session_root


def normalize_query(value: str) -> str:
    return value.strip().lower()


def matches_query(session: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    query = normalize_query(query)
    candidates = [
        str(session.get("file_name") or ""),
        str(session.get("title") or ""),
        str(session.get("pdf_path") or ""),
    ]
    return any(query in normalize_query(candidate) for candidate in candidates)


def find_recent_session(query: str | None = None) -> dict[str, Any]:
    sessions = list_session_states()
    if query:
        sessions = [session for session in sessions if matches_query(session, query)]

    if not sessions:
        return {
            "status": "empty",
            "session_root": str(session_root()),
            "message": "No matching active PDF sessions were found.",
            "query": query,
            "sessions": [],
        }

    current = sessions[0]
    return {
        "status": "ok",
        "session_root": str(session_root()),
        "query": query,
        "selected_session": current,
        "session_count": len(sessions),
        "sessions": sessions[:5],
        "human_summary": (
            f"The most recent session is {current.get('file_name')}. It is currently on "
            f"segment {current.get('current_segment')}/{current.get('total_segments')} "
            f"(pages {current.get('current_page_start')}-{current.get('current_page_end')})."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find the most recent persistent PDF reading session."
    )
    parser.add_argument(
        "--query",
        help="Optional file-name/title/path filter for selecting a session",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = find_recent_session(args.query)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
