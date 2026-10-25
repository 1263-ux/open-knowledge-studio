"""Shared classification vocabulary and source-material boundaries."""
from __future__ import annotations

DOMAIN_LABELS = dict(zip(
    ("management", "transport", "finance", "production", "computing", "repair",
     "engineering", "construction", "science", "agriculture", "social", "administration",
     "legal", "sales", "education", "personal", "media", "healthcare", "care", "maintenance", "food", "security"),
    ("管理", "交通运输", "金融", "生产制造", "计算与信息", "维修", "研发工程", "建筑",
     "科学", "农业", "社会", "行政", "法律", "销售", "教育", "个人成长", "传媒",
     "医疗健康", "照护", "维护", "食品", "安全"),
))
TYPE_DIRS = {
    "concept": "concepts", "concepts": "concepts",
    "strategy": "strategies", "strategies": "strategies",
    "anti-pattern": "anti-patterns", "anti-patterns": "anti-patterns",
}

def is_source_material(meta: dict) -> bool:
    # Explicit metadata only: titles and provisional status are not evidence.
    return (meta.get("content_role") == "source_material"
            or meta.get("source_type") == "local-ocr-import")

def validate_classification(area, wiki_type, *, skill: bool = False) -> tuple[str, str]:
    if not isinstance(area, str) or not area.strip():
        raise ValueError("Knowledge domain is required. Set draft_area or review with --area; candidate retained.")
    if area not in DOMAIN_LABELS and not (skill and area == "skills"):
        raise ValueError(f"Unknown knowledge domain: {area!r}. Use a canonical ID from oks wiki domains; candidate retained.")
    if not isinstance(wiki_type, str) or wiki_type not in TYPE_DIRS:
        raise ValueError("Wiki type is required: concept, strategy, anti-pattern. Set draft_type or review with --type; candidate retained.")
    return area, TYPE_DIRS[wiki_type]
