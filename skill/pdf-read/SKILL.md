---
name: pdf-read
description: Read, analyze, summarize, extract, convert, or batch-process PDF files with metadata-first, page-scoped, failure-transparent workflows.
---

<objective>Provide a strict, auditable workflow for any PDF reading or analysis task so outputs remain accurate and transparent.</objective>

<use_when>
- The user asks to read, analyze, or summarize a PDF
- The user needs specific information extracted from a PDF, such as keywords, formulas, or tables
- The PDF appears to be scanned or image-based and may require OCR
- Multiple PDFs need to be processed in batch
</use_when>

<process>

**STEP 0 - Confirm the task boundary (required)**

Before reading anything, classify the user goal as one of:
- A. Quick overview (structure, table of contents, themes)
- B. Specific page-range reading (the user provides pages)
- C. Full-document reading (small files only)
- D. Targeted extraction (keywords, formulas, tables, examples, definitions)
- E. OCR for scanned PDFs (image-based files)
- F. Batch processing (multiple PDFs)

**Default mode: B or D (safest).** Do not jump to full-document reading unless the user clearly asks for it.

---

**STEP 1 - Verify metadata (mandatory)**

Use system tools to read PDF metadata, such as `pdfinfo`, `mdls`, or an equivalent tool. Collect at least:
1. total pages
2. file size
3. author (metadata only)
4. creation date, if available

Rules:
- **Do not** infer metadata from the body text
- If metadata lookup fails, **report the failure clearly and stop** instead of guessing

Required display format:
- `path / pages / size / author / created_at(if available)`

---

**STEP 2 - Classify the PDF type (text vs scan)**

Determine whether the PDF is:
- **Text-based** (selectable text or extractable text exists)
- **Scanned/image-based** (text is not selectable and the file is mostly images)

If it is scanned/image-based:
- clearly state that **OCR is required for reliable reading**
- **do not** start OCR automatically; wait for explicit user confirmation

---

**STEP 3 - Choose a chunking strategy**

**3.1 Page thresholds**
- **> 200 pages**: do not read the whole file in one pass
  - read **30-50 pages** at a time
  - label each processed range explicitly, for example `p.1-50`
  - summarize only that range and do not extrapolate
- **51-200 pages**: chunking is recommended
  - read **20-40 pages** at a time
- **<= 50 pages**: a single pass is allowed, though structure-first reading is still preferred

**3.2 Every chunk output must include**
1. the processed page range
2. the key points from that range, in structured form
3. uncertainties or missing information in that range, if any
4. an optional recommendation for the next range to process

---

**STEP 4 - Strict accuracy mode**

Never fabricate:
- page counts
- author information
- publication details
- version information
- table of contents structure
- citation sources

If something cannot be confirmed from processed pages or metadata, explicitly write:
> "This information was not confirmed from metadata or the processed pages."

All summaries and analysis must:
- rely only on processed pages
- avoid cross-page extrapolation
- avoid filling in missing gaps

---

**STEP 5 - Failure transparency**

If any step fails, always:
1. report the exact failure point, such as `pdfinfo failed` or `text extraction failed`
2. offer possible alternatives, such as another tool, OCR, or a smaller page range
3. **stop** the analysis instead of continuing with assumptions

---

**STEP 6 - OCR rules for scanned PDFs**

If the user confirms OCR:
1. run OCR on a small sample first, ideally 1-3 pages
2. report OCR quality:
   - whether the typo/error rate is obviously high
   - whether tables and formulas remain usable
3. continue with larger OCR only after the user accepts the sample quality
4. label OCR-based output as:
   - `"OCR result, recognition errors may remain."`

---

**STEP 7 - Safety and file-operation rules**

Default to read-only behavior. Do not write, convert, or delete files unless the user asks.

**7.1 No implicit conversion**
Do not automatically:
- convert to txt, md, or doc
- generate duplicate copies
- compress, merge, or split files

If the user requests conversion or output files:
- list the file paths and count that will be created
- state whether anything will be overwritten
- wait for confirmation before proceeding

**7.2 Temporary files and cache**
If temporary files are required:
- write them under a project-local `temp/` directory
- mention cleanup options at the end of the task
- never delete them automatically

---

**STEP 8 - Output rules**

Unless the user explicitly asks for rewriting or polishing:
- preserve the original paragraph structure
- use short direct quotes for key definitions, theorems, or formulas when possible
- summarize at a higher level without changing the original meaning

</process>

<execution_template>
When the user says "read/analyze this PDF", the assistant response must include, in order:
1. metadata (STEP 1 output)
2. the PDF type classification (STEP 2)
3. the reading plan and page/chunk range (STEP 3)
4. "I will rely only on processed pages and will not extrapolate beyond them." (STEP 4)
5. a note that any failure will be reported and analysis will stop (STEP 5)
</execution_template>

<success_criteria>
- Metadata was verified and shown
- The PDF type was classified (text-based or scanned)
- A chunking strategy was selected and followed
- All outputs are grounded in processed pages only
- Any failure was reported explicitly
</success_criteria>
