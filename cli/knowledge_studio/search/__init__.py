"""OKS 可插拔 search backend。

内置 backend：
- **native**（默认）：6+1 因子 + jieba + IDF + title boost，无新依赖，实时遍历
- **fts5**（CV from TreeSearch shibing624 FTS5Index）：SQLite FTS5 + BM25 +
  持久化索引 + 增量 diff，大数据场景（1000+ wiki）比 native 遍历快
- **fusion**：native 主 top-3 + fts5 补盲 2，实验验证最优（R@1 0.667）

connector 扩展点（关键架构决策）：
第三方可通过 ``entry_points(group="oks_search_backend")`` 注册新 backend
（如 embedding / 代码搜索 ast_parser / 其他开源 search 框架），
recall 切 ``search_backend`` 配置即用，OKS 核心无需改。

config: ``search_backend: native | fts5 | fusion | <connector-name>``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SearchHit:
    """A single search result from any backend."""

    slug: str
    title: str
    score: float
    backend: str = "native"
    extra: dict[str, Any] = field(default_factory=dict)


class SearchBackend(Protocol):
    """可插拔 search backend 接口。

    第三方实现只需满足：
    - ``search(query, *, limit, scope, **kwargs) -> list[SearchHit]``
    - ``index(pages)`` 预索引（native 可 no-op，fts5/embedding 需要）

    scope 是 area 硬过滤（comma-separated），不设默认全部。
    """

    def index(self, pages: list[dict[str, Any]]) -> None:
        """索引 wiki pages。native 实时计算可 no-op；fts5/embedding 预索引。"""
        ...

    def search(
        self, query: str, *, limit: int = 10, scope: str | None = None, **kwargs: Any
    ) -> list[SearchHit]:
        """返回 ranked hits。score 越高越相关。"""
        ...


def get_backend(name: str = "native", root: str | None = None, **kwargs: Any) -> SearchBackend:
    """按名字取 backend。

    native / fts5 / fusion 内置；其他名字查 connector entry_points
    (group="oks_search_backend")，找不到则 ValueError。
    """
    n = (name or "native").lower()
    if n in ("native", "treesearch"):
        # v0.6.0: native 默认改用 TreeSearch（structure-aware FTS5）
        # 语义改写 case 比 jieba+IDF 提升 40%。用户不感知切换。
        from .treesearch_backend import TreeSearchBackend

        return TreeSearchBackend(root=root, **kwargs)
    if n == "legacy":
        # 旧 native（jieba+IDF 6+1），保留供对比/回退
        from .native import NativeBackend

        return NativeBackend()
    if n == "fts5":
        from .fts5 import FTS5Backend

        return FTS5Backend(root=root, **kwargs)
    if n == "fusion":
        from .fusion import FusionBackend

        return FusionBackend(root=root, **kwargs)
    # connector 扩展点：第三方 entry_points
    try:
        from importlib.metadata import entry_points

        for ep in entry_points(group="oks_search_backend"):
            if ep.name == n:
                return ep.load()(root=root, **kwargs)
    except Exception:
        pass
    raise ValueError(
        f"unknown search backend: {name!r}. available: native, fts5, fusion "
        f"(+ connector entry_points group='oks_search_backend')"
    )


__all__ = ["SearchHit", "SearchBackend", "get_backend"]
