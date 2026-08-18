"""TreeSearch backend — OKS 默认召回（structure-aware FTS5，CV from shibing624/TreeSearch）。

v0.6.0 起 native 默认改用 TreeSearch 算法：
- structure-aware FTS5（heading 层级 + 段落级 node），非 page-level
- 无向量嵌入、无分块，毫秒级搜上万文档
- 语义改写 case 比 jieba+IDF 提升 40%（eval 10-case: 60%→100%）

用户不感知切换：``search_backend: native`` 仍可用，但内部走 TreeSearch。
保留旧 native（jieba+IDF）为 ``legacy`` backend 供对比/回退。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import SearchHit


class TreeSearchBackend:
    """包装 ``treesearch.TreeSearch`` — structure-aware FTS5 默认召回。

    索引 wiki/ 目录（lazy，首次 search 时建索引并缓存实例）。
    scope 按 area 硬过滤（path 包含 wiki/<area>/）。
    """

    def __init__(self, root: str | None = None, **kwargs: Any) -> None:
        self._root = Path(root) if root else None
        self._ts = None  # lazy
        self._indexed_path: str | None = None

    def _wiki_root(self) -> Path:
        if self._root:
            return self._root / "wiki"
        from ..store import repo_root
        return repo_root() / "wiki"

    def _ensure_indexed(self) -> Any:
        wiki_dir = self._wiki_root()
        path = str(wiki_dir)
        # 路径变了或首次——重建
        if self._ts is None or self._indexed_path != path:
            from treesearch import TreeSearch

            self._ts = TreeSearch(path)
            self._indexed_path = path
        return self._ts

    def index(self, pages: list[dict[str, Any]]) -> None:
        """TreeSearch lazy 索引，无需预建。首次 search 时触发。"""
        return None

    def search(
        self, query: str, *, limit: int = 10, scope: str | None = None, **kwargs: Any
    ) -> list[SearchHit]:
        ts = self._ensure_indexed()
        # TreeSearch top_k 取 limit*2 便于 scope 过滤后仍有足够
        raw = ts.search(query, top_k=max(limit * 3, limit))
        hits: list[SearchHit] = []
        for doc in raw.get("documents", []):
            doc_id = doc.get("doc_id", "")
            # scope 硬过滤：doc_id 路径含 area
            if scope:
                areas = [a.strip() for a in scope.split(",") if a.strip()]
                if not any(f"/{a}/" in doc_id or doc_id.startswith(a) for a in areas):
                    continue
            # 取该 doc 最高分 node 的 score 作 page score
            nodes = doc.get("nodes", [])
            best = max(nodes, key=lambda n: n.get("score", 0)) if nodes else {}
            score = float(best.get("score", 0.0))
            title = best.get("title", doc_id)
            hits.append(
                SearchHit(
                    slug=doc_id,
                    title=title,
                    score=score,
                    backend="treesearch",
                    extra={
                        "node_count": len(nodes),
                        "best_node": best.get("title", ""),
                        "line": best.get("line_start"),
                    },
                )
            )
            if len(hits) >= limit:
                break
        return hits


__all__ = ["TreeSearchBackend"]
