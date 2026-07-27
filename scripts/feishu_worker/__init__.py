"""Feishu worker modules — configuration, CLI wrappers, processing stages.

Leaf modules (zero imports from feishu_base_worker):
  config        — WorkerConfig, load_config, Lark CLI resolver
  io_utils      — atomic writes, hashing, redaction, scalar_cell
  base_client   — lark_json, record CRUD, retry helpers
  claim         — parse_base_datetime, is_candidate, lease lock, claim/release
  capture       — extract_url, normalize_attachments, capture_envelope, hashing
  source_router — connector binary, _run_or_validate, Raw packaging variants
"""
