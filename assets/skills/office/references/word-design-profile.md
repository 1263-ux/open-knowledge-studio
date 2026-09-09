# OKS Word design profile

The Word adapter follows the reusable shape used by mature template-driven
Office skills: `extract → verify → generate → render`. A profile is a small,
portable description of a template's page geometry, fonts, palette, and table
geometry. It contains no private document body or knowledge claims.

## Default profile

Without a user template, OKS uses the bundled `oks-word/v1` profile:

- fixed A4-compatible margins and a fixed table width;
- Aptos/Microsoft YaHei typography;
- dark blue header, light alternating rows, explicit borders and cell margins;
- fixed DXA column widths, repeated header row, vertical centering, and numeric alignment;
- evidence status/source information as a subdued note below each table.

This is a designed scratch profile, not a claim that a user's brand has been
learned. For a real template, extract a profile locally:

```powershell
python assets/skills/office/scripts/extract_word_profile.py `
  --template C:\path\to\template.docx `
  --output tmp/oks-word-profile.json
```

Then render with it:

```powershell
python assets/skills/office/scripts/build_office.py `
  --package tmp/oks-office-evidence.json `
  --format docx `
  --word-profile tmp/oks-word-profile.json `
  --output output/report.docx
```

The extractor learns only page margins, base fonts, and the first table's
width/palette. It does not upload or commit the template. A supplied template
that requires preserving its actual shell, headers, footers, or complex
components must still use the `documents` production workflow; a profile alone
is not a full template clone.

## Verification contract

`validate_docx.py` checks that generated tables are fixed-layout OOXML tables,
have explicit DXA cell widths, shaded headers, and repeating header rows. It
does not replace LibreOffice/Word rendering: overflow and pagination remain
visual QA concerns.
