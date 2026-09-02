"""路由模块：/api/v1 端点按域拆分（messages/thumb/stats/config/ops）。

各模块只暴露 build_*_router(ctx)，共享鉴权依赖与 WebContext 见 deps。
"""

from __future__ import annotations

from app.web.routes.deps import WebContext, require_auth  # noqa: F401
