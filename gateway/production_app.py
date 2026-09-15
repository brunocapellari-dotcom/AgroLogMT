from __future__ import annotations

from .app import app
from .pecuaria_routes import router as pecuaria_router

app.include_router(pecuaria_router)

__all__ = ["app"]
