"""Fusion backend — native 主 top-3 + fts5 补盲 2。

实验验证最优（15 模糊 query）：
- native scoped+goal: R@1=0.600, MRR=0.689
- fts5 alone: R@1=0.133（差，但独有命中 4 个 native 漏的）
- RRF 1:1: R@1=0.467（fts5 噪声稀释 native top-1）
- **fusion (native主+fts5补盲)**: R@1=0.667, MRR=0.722 ✅

设计：native 保 R@1 优势（6+1 因子 + scope/goal boost），fts5 补 native 漏的
（BM25 + 结构化关键词命中 native 的 substring 盲区）。
"""
from __future__ import annotations

from typing import Any

from . import SearchHit


class FusionBackend:
    """native 主排序 + fts5 独有补盲。

    - native 取 top-N（默认 3）作主排序
    - fts5 取全部候选，去重后补 M 个（默认 2）native 没命中的
    - 最终 = native top-N + fts5 独有 M

    参数可调（实验数据支持调优，非盲调）。
    """

    def __init__(
        self,
        root: str | None = None,
        native_top: int = 3,
        fts5_supplement: int = 2,
        **kwargs: Any,
    ) -> None:
        from .native import NativeBackend
        from .fts5 import FTS5Backend

        self._native = NativeBackend()
        self._fts5 = FTS5Backend(root=root, **{
            k: v for k, v in kwargs.items() if k in ("db_path", "weights")
        })
        self._native_top = native_top
        self._fts5_supplement = fts5_supplement

    def index(self, pages: list[dict[str, Any]]) -> None:
        """native no-op；fts5 预索引。"""
        self._native.index(pages)
        self._fts5.index(pages)

    def search(
        self, query: str, *, limit: int = 10, scope: str | None = None, **kwargs: Any
    ) -> list[SearchHit]:
        # native 主排序（保 R@1）
        native_hits = self._native.search(
            query, limit=max(self._native_top, limit), scope=scope, **kwargs
        )
        # fts5 补盲候选
        fts5_hits = self._fts5.search(query, limit=limit * 2, scope=scope, **kwargs)

        seen = {h.slug for h in native_hits}
        supplement = [
            h for h in fts5_hits if h.slug not in seen
        ][: self._fts5_supplement]

        # native top-N + fts5 独有 M，截到 limit
        return (native_hits[: self._native_top] + supplement)[:limit]


__all__ = ["FusionBackend"]
