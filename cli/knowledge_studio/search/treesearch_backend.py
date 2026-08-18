"""TreeSearch backend — OKS 默认召回（structure-aware FTS5，CV from shibing624/TreeSearch）。

v0.6.0 起 native 默认改用 TreeSearch 算法：
- structure-aware FTS5（heading 层级 + 段落级 node），非 page-level
- 无向量嵌入、无分块，毫秒级搜上万文档
- 语义改写 case 比 jieba+IDF 提升 40%（eval 10-case: 60%→100%）

实现细节：TreeSearch 的 markdown parser 只索引 ``#`` heading 之间的内容，
不处理 YAML frontmatter，也不索引无 heading 的纯文本 body。
本 backend 用 list_wiki_pages 拿到已解析的 page（slug+title+body），
写到 cache 目录的 ``<slug>.md`` = ``# {title}\\n\\n{body}``（保证有 H1 + 去 frontmatter），
再让 TreeSearch 索引 cache。search 后 doc_id=slug 直接映射。

用户不感知切换：``search_backend: native`` 仍可用，内部走 TreeSearch。
保留旧 native（jieba+IDF）为 ``legacy`` backend 供对比/回退。
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from . import SearchHit

_CACHE_DIR = ".oks-treesearch-cache"


class TreeSearchBackend:
    """包装 ``treesearch.TreeSearch`` — structure-aware FTS5 默认召回。

    维护一个 cache 目录（<kb_root>/.oks-treesearch-cache/<slug>.md），
    内容是 ``# {title}\\n\\n{body}``（保证 H1 + 去 frontmatter）。
    按内容 hash 增量更新（变了才重写）。
    """

    def __init__(self, root: str | None = None, **kwargs: Any) -> None:
        self._root = Path(root) if root else None
        self._ts = None
        self._cache_dir: Path | None = None
        self._indexed_hash: str | None = None

    def _kb_root(self) -> Path:
        if self._root:
            return self._root
        from ..store import repo_root
        return repo_root()

    def _rebuild_cache_if_needed(self) -> str:
        """把 wiki pages 写成清洁 cache（# title + body），返回内容 hash。"""
        from ..store import list_wiki_pages

        kb = self._kb_root()
        cache = kb / _CACHE_DIR
        cache.mkdir(parents=True, exist_ok=True)

        pages = list_wiki_pages()
        hasher = hashlib.sha256()
        written: set[str] = set()
        for p in pages:
            slug = p.get("slug", "")
            if not slug:
                continue
            title = p.get("title", slug)
            body = p.get("body", "")
            content = f"# {title}\n\n{body}"
            hasher.update(content.encode("utf-8"))
            (cache / f"{slug}.md").write_text(content, encoding="utf-8")
            written.add(slug)
        # 清理已删 page 的 cache 文件
        for f in cache.glob("*.md"):
            if f.stem not in written:
                f.unlink(missing_ok=True)
        return hasher.hexdigest()

    def _ensure_indexed(self) -> Any:
        content_hash = self._rebuild_cache_if_needed()
        cache_path = str(self._kb_root() / _CACHE_DIR)
        if self._ts is None or self._indexed_hash != content_hash:
            from treesearch import TreeSearch

            self._ts = TreeSearch(cache_path)
            self._indexed_hash = content_hash
        return self._ts

    def index(self, pages: list[dict[str, Any]]) -> None:
        """首次 search 时 lazy 建 cache + 索引。"""
        return None

    def search(
        self, query: str, *, limit: int = 10, scope: str | None = None, **kwargs: Any
    ) -> list[SearchHit]:
        ts = self._ensure_indexed()
        raw = ts.search(query, top_k=max(limit * 3, limit))
        hits: list[SearchHit] = []
        for doc in raw.get("documents", []):
            doc_id = doc.get("doc_id", "")
            if scope:
                areas = [a.strip() for a in scope.split(",") if a.strip()]
                if not any(f"/{a}/" in doc_id or doc_id.startswith(a) for a in areas):
                    continue
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
