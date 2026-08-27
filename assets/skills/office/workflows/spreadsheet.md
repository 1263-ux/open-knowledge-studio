# Excel workflow

For ordinary `.xlsx` creation, analysis, and edits, use the host
`spreadsheets` workflow. Preserve formulas as formulas, retain data validation,
named ranges, formats, filters, freeze panes, and chart references where the
task requires them. Its own validation is the production check; this Office
skill does not advertise a separate local XLSX builder.

Render or open representative worksheet views after writing. Verify formulas,
visible values, totals, number formats, column widths, and error cells; a ZIP
that opens is not sufficient.

Requests involving Power Query, Power Pivot/Data Model, native PivotTables,
VBA, or a live desktop workbook route to `excel-native` only when its Windows
and desktop-Excel probe passes. Otherwise report `environment_limited` and
offer a normal-XLSX alternative without claiming native feature parity.
