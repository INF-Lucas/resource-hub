# pdf-read

`pdf-read` is a metadata-first PDF reading skill for GitHub distribution.

It is designed for reading, analyzing, extracting, and summarizing PDF files
with a strict workflow:

1. verify metadata first
2. detect whether the PDF is text-based or scanned
3. choose a safe page-scoped reading plan
4. return only page-grounded results
5. stop clearly when extraction fails

This GitHub package is a release copy of the original Claude Code skill. The
source skill under `~/.claude/skills/pdf-read` is not modified by this
repository.

## Highlights

- Metadata verification before any reading
- Text-PDF vs scan-PDF detection before extraction
- Chunked reading rules for medium and large files
- Strict page-grounded accuracy rules
- Failure-transparent behavior instead of guesswork
- OCR treated as opt-in with sample quality checks

## Typical Use Cases

- Get a safe overview of a PDF before reading it
- Read a specific page range
- Extract keywords, formulas, tables, or definitions
- Decide whether OCR is required for a scanned PDF
- Process multiple PDFs with an explicit scope

## Suggested Tooling

- `pdfinfo`
- `pdftotext`
- `mdls`
- OCR tools when the user explicitly confirms OCR

## Repository Layout

```text
pdf-read/
├── SKILL.md
├── README.md
├── LICENSE.md
├── skill.json
└── agents/
```

## Notes

- The instruction body in `SKILL.md` preserves the original Chinese workflow
  because that is the source behavior currently used in Claude Code.
- This release copy exists for GitHub organization and future public packaging.

## License

Released under the `MIT` license.
