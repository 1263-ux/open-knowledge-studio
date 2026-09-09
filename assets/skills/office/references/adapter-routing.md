# Office adapter routing

Probe local availability before selecting an optional Adapter. A missing
Adapter is a normal `environment_limited` result, not an installation request
or a hidden default dependency.

| Task | Preferred route | Fallback / boundary |
|---|---|---|
| Create or edit DOCX | Independently installed Anthropic `docx` host skill; otherwise host `documents` skill | Local deterministic DOCX builder only for simple, labeled fallback output |
| Revise an open Word document with tracked changes/comments | `word-live` optional Adapter | Do not emulate a live revision with untracked XML changes |
| Create regular XLSX | Host `spreadsheets` skill / openpyxl | Preserve formulas and use worksheet rendering QA |
| Power Query, Data Model, PivotTable, native VBA | `excel-native` optional Adapter | Requires its supported Windows desktop Excel workstation |
| Create ordinary PPTX | Host `presentations` skill | Local python-pptx output is serialization smoke only |
| High-design or template-intensive PPTX | `ppt-master` optional Adapter | Use only after local probe and full slide visual review |
| PDF | Host `pdf` skill or controlled local conversion | CJK output requires an explicit readable font |
| Read DOCX/PPTX/XLSX | `office.markitdown` intake | Preserve parser limits and inspect original layout when needed |
