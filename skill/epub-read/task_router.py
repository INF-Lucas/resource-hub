"""
Generate auditable EPUB task plans for task-mode driven reading workflows.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from utils import ensure_dir, load_json

Mode = Literal["overview", "targeted_read", "full_read", "extract", "complex_content", "batch"]
ExtractionType = Literal[
    "keywords",
    "quotes",
    "examples",
    "definitions",
    "action_items",
    "names",
    "locations",
    "organizations",
    "tables",
    "lists",
]

DEFAULT_EXTRACTION_TYPES: list[ExtractionType] = ["keywords", "definitions", "quotes"]
MAX_TARGETED_CHAPTERS = 5
MAX_TARGETED_CHUNKS = 10
FULL_READ_WINDOW = 3


@dataclass
class TaskPlan:
    mode: Mode
    requires_parse: bool
    requires_chunking: bool
    target_chapters: list[str] = field(default_factory=list)
    target_chunks: list[str] = field(default_factory=list)
    keyword: str | None = None
    extraction_types: list[str] = field(default_factory=list)
    recommended_files: list[str] = field(default_factory=list)
    session_state_update: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    input_paths: list[str] = field(default_factory=list)
    batch_mode: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return load_json(path)
    except Exception:
        return {}
    return {}


def chunk_filename(index: int) -> str:
    return f"chunks/chunk-{index:04d}.md"


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def resolve_book_dir(input_path: Path) -> tuple[Path, bool]:
    if input_path.is_dir():
        is_parsed = (input_path / "manifest.json").exists() and (input_path / "book.json").exists()
        return input_path, is_parsed

    if input_path.is_file() and input_path.suffix.lower() == ".epub":
        projected = input_path.parent / ".epub_read_output" / input_path.stem
        return projected, False

    raise FileNotFoundError(f"Path does not exist or is not a supported input: {input_path}")


def chapter_file_map(book: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for chapter in book.get("chapters", []):
        chapter_id = chapter.get("chapter_id", "")
        chapter_file = chapter.get("chapter_file", "")
        if chapter_id and chapter_file:
            mapping[chapter_id] = f"chapters/{Path(chapter_file).name}"
    return mapping


def reading_index_map(reading_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        chapter.get("chapter_id", ""): chapter
        for chapter in reading_index.get("chapters", [])
        if chapter.get("chapter_id")
    }


def chapter_start_chunk(chapter_id: str, reading_index: dict[str, Any], manifest: dict[str, Any]) -> int | None:
    chapter_lookup = reading_index_map(reading_index)
    chapter_entry = chapter_lookup.get(chapter_id)
    if chapter_entry and chapter_entry.get("chunk_start"):
        return int(chapter_entry["chunk_start"])

    for chunk in manifest.get("chunks", []):
        if chunk.get("chapter_id") == chapter_id:
            return int(chunk.get("chunk_index", 0)) or None
    return None


def normalize_extraction_types(raw_types: list[str] | None) -> list[str]:
    if not raw_types:
        return list(DEFAULT_EXTRACTION_TYPES)
    return unique_preserve_order(raw_types)


def expand_batch_inputs(raw_paths: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_file() and path.suffix.lower() == ".epub":
            expanded.append(str(path))
            continue
        if path.is_dir():
            for epub_file in sorted(path.rglob("*.epub")):
                expanded.append(str(epub_file.resolve()))
    return unique_preserve_order(expanded)


def build_base_plan(mode: Mode) -> TaskPlan:
    return TaskPlan(
        mode=mode,
        requires_parse=False,
        requires_chunking=False,
        session_state_update={"current_mode": mode, "updated_at": now_iso()},
    )


def route_task(book_dir: Path, mode: Mode, params: dict[str, Any] | None = None) -> TaskPlan:
    params = params or {}
    plan = build_base_plan(mode)
    plan.keyword = params.get("keyword")
    if params.get("extraction_types"):
        plan.extraction_types = normalize_extraction_types(params.get("extraction_types"))

    if mode == "batch":
        raw_input_paths = params.get("input_paths", [])
        plan.batch_mode = params.get("batch_mode", "parse")
        plan.input_paths = expand_batch_inputs(raw_input_paths)
        if params.get("extraction_types"):
            plan.extraction_types = normalize_extraction_types(params.get("extraction_types"))
        plan.requires_parse = plan.batch_mode in {"parse", "all", "extract", "overview"}
        if not plan.input_paths:
            plan.notes.append("No processable EPUB files were found. Pass files or directories via --input-paths.")
        else:
            plan.notes.append(f"Detected {len(plan.input_paths)} EPUB inputs.")
            if plan.batch_mode in {"extract", "all"}:
                plan.notes.append("For batch extraction, process books incrementally to avoid loading too much output at once.")
        plan.recommended_files = []
        return plan

    manifest_path = book_dir / "manifest.json"
    book_path = book_dir / "book.json"
    reading_index_path = book_dir / "reading_index.json"
    session_state_path = book_dir / "session_state.json"
    complex_content_path = book_dir / "complex_content.json"

    is_parsed = manifest_path.exists() and book_path.exists()
    if not is_parsed:
        plan.requires_parse = True
        plan.recommended_files = []
        plan.notes.append("Run parse_epub.py first to parse the EPUB.")
        return plan

    manifest = safe_load_json(manifest_path)
    book = safe_load_json(book_path)
    reading_index = safe_load_json(reading_index_path)
    session_state = safe_load_json(session_state_path)
    chapter_files = chapter_file_map(book)
    chapter_ids = list(chapter_files.keys())

    chunk_count = int(manifest.get("chunk_count", 0))
    is_chunked = chunk_count > 0

    if mode == "overview":
        plan.recommended_files = unique_preserve_order(
            [
                "metadata.json",
                "toc.json",
                "manifest.json",
                "reading_index.json",
                "complex_content.json" if complex_content_path.exists() else "",
            ]
        )
        plan.notes.extend(
            [
                "Read only metadata, the table of contents, and statistics. Do not load the body text by default.",
                "Use targeted_read or full_read for deeper reading.",
            ]
        )
        return plan

    if mode == "targeted_read":
        requested_chapters = unique_preserve_order(params.get("chapter_ids", []))
        chunk_start = params.get("chunk_start")
        chunk_end = params.get("chunk_end")

        if requested_chapters:
            valid_chapters = [chapter_id for chapter_id in requested_chapters if chapter_id in chapter_ids]
            if len(valid_chapters) > MAX_TARGETED_CHAPTERS:
                valid_chapters = valid_chapters[:MAX_TARGETED_CHAPTERS]
                plan.notes.append(
                    f"Reading is capped at {MAX_TARGETED_CHAPTERS} chapters per request; the selection was truncated automatically."
                )
            if not valid_chapters:
                plan.notes.append("No matching chapter IDs were found. Check toc.json or reading_index.json first.")
            plan.target_chapters = valid_chapters
            plan.recommended_files = [chapter_files[chapter_id] for chapter_id in valid_chapters]
            if valid_chapters:
                plan.session_state_update.update(
                    {
                        "current_chapter_id": valid_chapters[0],
                        "last_action": "targeted_read",
                    }
                )
            return plan

        if chunk_start is not None or chunk_end is not None:
            if not is_chunked:
                plan.requires_chunking = True
                plan.notes.append("This book has not been chunked yet. Run chunk_book.py first.")
                return plan

            start = int(chunk_start or chunk_end or 1)
            end = int(chunk_end or chunk_start or start)
            if end < start:
                start, end = end, start
            if end - start + 1 > MAX_TARGETED_CHUNKS:
                end = start + MAX_TARGETED_CHUNKS - 1
                plan.notes.append(
                    f"Reading is capped at {MAX_TARGETED_CHUNKS} chunks per request; the range was truncated automatically."
                )

            start = max(1, start)
            end = min(chunk_count, end)
            plan.target_chunks = [chunk_filename(index) for index in range(start, end + 1)]
            plan.recommended_files = list(plan.target_chunks)
            plan.session_state_update.update(
                {
                    "current_chunk": start,
                    "last_action": "targeted_read",
                }
            )
            manifest_chunks = manifest.get("chunks", [])
            if manifest_chunks and 0 < start <= len(manifest_chunks):
                plan.session_state_update["current_chapter_id"] = manifest_chunks[start - 1].get("chapter_id")
            return plan

        if plan.keyword:
            plan.recommended_files = ["manifest.json", "reading_index.json", "toc.json"]
            plan.notes.extend(
                [
                    "For keyword lookup, search chapters/ or chunks/ first, then return to targeted_read for close reading.",
                    "If the book is chunked, prefer searching chunks/ to keep context smaller.",
                ]
            )
            plan.session_state_update["last_action"] = "keyword_lookup"
            plan.session_state_update["last_query"] = plan.keyword
            return plan

        plan.notes.append("Provide --chapter / --chapter-id / --chunk-start / --chunk-end / --keyword.")
        return plan

    if mode == "full_read":
        if not is_chunked:
            plan.requires_chunking = True
            plan.notes.append("full_read requires chunk files, so run chunk_book.py first.")
            return plan

        current_chunk = int(session_state.get("current_chunk") or 0)
        start_chunk = 1
        last_action = "read_chunk"

        if params.get("continue_read"):
            start_chunk = current_chunk + 1 if current_chunk else 1
            last_action = "continue_read"
        elif params.get("previous_chunk"):
            start_chunk = current_chunk - 1 if current_chunk else 1
            last_action = "previous_chunk"
        elif params.get("next_chunk"):
            start_chunk = current_chunk + 1 if current_chunk else 1
            last_action = "next_chunk"
        elif params.get("start_chunk") is not None:
            start_chunk = int(params["start_chunk"])
            last_action = "jump_to_chunk"
        elif params.get("start_chapter"):
            chapter_id = str(params["start_chapter"])
            chapter_chunk = chapter_start_chunk(chapter_id, reading_index, manifest)
            if chapter_chunk is not None:
                start_chunk = chapter_chunk
                last_action = "jump_to_chapter"
            else:
                plan.notes.append("The requested chapter is not mapped to chunks yet, so reading will start from chunk 1.")
        elif current_chunk:
            start_chunk = current_chunk

        start_chunk = max(1, min(chunk_count, start_chunk))
        end_chunk = min(chunk_count, start_chunk + FULL_READ_WINDOW - 1)
        plan.target_chunks = [chunk_filename(index) for index in range(start_chunk, end_chunk + 1)]
        plan.recommended_files = list(plan.target_chunks)

        manifest_chunks = manifest.get("chunks", [])
        current_chapter_id = None
        if manifest_chunks and 0 < start_chunk <= len(manifest_chunks):
            current_chapter_id = manifest_chunks[start_chunk - 1].get("chapter_id")

        plan.session_state_update.update(
            {
                "current_chunk": start_chunk,
                "current_chapter_id": current_chapter_id,
                "last_action": last_action,
            }
        )
        plan.notes.extend(
            [
                "Read at most 1-3 chunks per turn to avoid loading an entire long book at once.",
                "When continuing, prefer the position recorded in session_state.json.",
            ]
        )
        return plan

    if mode == "extract":
        plan.extraction_types = normalize_extraction_types(params.get("extraction_types"))
        if is_chunked:
            plan.recommended_files = [chunk_filename(index) for index in range(1, chunk_count + 1)]
            plan.notes.append("Extraction mode will scan chunks incrementally, which is better for long books.")
        else:
            plan.recommended_files = [chapter_files[chapter_id] for chapter_id in chapter_ids]
            if len(plan.recommended_files) > 20:
                plan.notes.append("This book is not chunked yet; run chunk_book.py first to improve extraction precision.")

        plan.session_state_update.update(
            {
                "last_action": "extract",
                "last_query": plan.keyword or ",".join(plan.extraction_types),
            }
        )
        return plan

    if mode == "complex_content":
        plan.recommended_files = unique_preserve_order(
            [
                "complex_content.json" if complex_content_path.exists() else "",
                "manifest.json",
                "reading_index.json",
            ]
        )
        plan.session_state_update["last_action"] = "complex_content_scan"
        plan.notes.extend(
            [
                "Prioritize complex_content.json and manifest.json; do not open the body text by default.",
                "Focus on image-heavy chapters, SVG resources, and low-text high-resource chapters.",
            ]
        )
        return plan

    raise ValueError(f"Unknown mode: {mode}")


def plan_to_dict(plan: TaskPlan) -> dict[str, Any]:
    data = asdict(plan)
    data["mode"] = str(plan.mode)
    return data


def save_plan(output_path: Path, plan: TaskPlan) -> Path:
    ensure_dir(output_path.parent)
    output_path.write_text(
        json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route EPUB reading tasks and generate an execution plan.")
    parser.add_argument(
        "path",
        nargs="?",
        help="A parsed book directory, an EPUB file to parse, or a single input path in batch mode",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["overview", "targeted_read", "full_read", "extract", "complex_content", "batch"],
        help="Task mode",
    )
    parser.add_argument("--chapter", action="append", help="Target chapter ID (can be repeated)")
    parser.add_argument("--chapter-id", action="append", help="Alias for target chapter ID")
    parser.add_argument("--chunk-start", type=int, help="Starting chunk index (1-based)")
    parser.add_argument("--chunk-end", type=int, help="Ending chunk index (1-based)")
    parser.add_argument("--chunk-range", type=str, help="Legacy compatible argument in the form start-end")
    parser.add_argument("--keyword", type=str, help="Keyword for targeted_read or extract")
    parser.add_argument(
        "--extraction-types",
        nargs="+",
        choices=[
            "keywords",
            "quotes",
            "examples",
            "definitions",
            "action_items",
            "names",
            "locations",
            "organizations",
            "tables",
            "lists",
        ],
        help="Extraction types (multiple allowed)",
    )
    parser.add_argument("--continue", dest="continue_read", action="store_true", help="Continue to the next chunk from session_state")
    parser.add_argument("--previous", dest="previous_chunk", action="store_true", help="Read the previous chunk")
    parser.add_argument("--next", dest="next_chunk", action="store_true", help="Read the next chunk")
    parser.add_argument("--start-chapter", type=str, help="Start full-book reading from a specific chapter")
    parser.add_argument("--start-chunk", type=int, help="Start full-book reading from a specific chunk")
    parser.add_argument("--input-paths", nargs="+", help="List of files or directories in batch mode")
    parser.add_argument(
        "--batch-mode",
        choices=["parse", "overview", "extract", "all"],
        default="parse",
        help="Processing strategy for batch mode",
    )
    parser.add_argument("--output", type=str, help="Output path for the generated plan")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.mode != "batch" and not args.path:
        print("Error: non-batch mode requires a book_dir or EPUB file path.", file=sys.stderr)
        return 1

    try:
        if args.mode == "batch":
            planning_root = Path.cwd()
            if args.path:
                planning_root = Path(args.path).expanduser().resolve().parent if Path(args.path).exists() else Path.cwd()
            raw_input_paths = list(args.input_paths or [])
            if args.path:
                raw_input_paths.insert(0, args.path)
            plan = route_task(
                planning_root,
                "batch",
                {
                    "input_paths": raw_input_paths,
                    "batch_mode": args.batch_mode,
                    "extraction_types": args.extraction_types,
                    "keyword": args.keyword,
                },
            )
            default_output = planning_root / ".task_plan.json"
        else:
            input_path = Path(args.path).expanduser().resolve()
            book_dir, _ = resolve_book_dir(input_path)

            chapter_ids = unique_preserve_order(list(args.chapter or []) + list(args.chapter_id or []))
            chunk_start = args.chunk_start
            chunk_end = args.chunk_end
            if args.chunk_range:
                start_text, end_text = args.chunk_range.split("-", 1)
                chunk_start = int(start_text)
                chunk_end = int(end_text)

            plan = route_task(
                book_dir,
                args.mode,
                {
                    "chapter_ids": chapter_ids,
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "keyword": args.keyword,
                    "extraction_types": args.extraction_types,
                    "continue_read": args.continue_read,
                    "previous_chunk": args.previous_chunk,
                    "next_chunk": args.next_chunk,
                    "start_chapter": args.start_chapter,
                    "start_chunk": args.start_chunk,
                },
            )
            default_output = (book_dir / ".task_plan.json") if book_dir.exists() else (Path.cwd() / ".task_plan.json")

        output_path = Path(args.output).expanduser().resolve() if args.output else default_output.resolve()
        save_plan(output_path, plan)

        print(json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2))
        print(f"\nExecution plan saved to: {output_path}", file=sys.stderr)
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
