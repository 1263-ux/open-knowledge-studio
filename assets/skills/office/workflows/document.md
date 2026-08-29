# Word workflow

Use the validated evidence package and a provided template before selecting a
generator. For a host with Anthropic's independently installed `docx` skill,
use that skill directly for DOCX creation and editing; do not copy its
instructions into OKS. Otherwise use the host `documents` skill.

For a supplied template, preserve its document shell, styles, headers,
footers, and layouts. A local profile may capture reusable margins, fonts, and
table geometry, but it is not a substitute for editing the original template.

If neither mature route is available, report `environment_limited`. For a
currently open document requiring tracked changes or comments, route to
`word-live`; do not silently replace the document with a regenerated clean
copy. Render and inspect every page before delivery.
