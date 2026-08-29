# Office quality gates

Every route has four gates. A successful library call is only file creation.

1. **Evidence:** package validation passes; all material claims map to sources;
   external URLs, retrieval times, and evidence statuses are retained.
2. **Structure:** the native file opens; formulas and links are preserved where
   applicable; format-specific validators pass.
3. **Visual:** render every page, slide, or relevant worksheet view and inspect
   clipping, overflow, blank regions, glyphs, tables, contrast, and template
   fidelity.
4. **Delivery:** return editable output, source ledger, and a delivery record
   containing Adapter, version, structural QA, visual QA, and any environmental
   limitation. Keep the evidence package as internal provenance unless the user
   asks for it.

If a renderer is unavailable, the delivery record must say
`visual_qa: unavailable` and name the required human check. It must not say
that visual QA passed.
