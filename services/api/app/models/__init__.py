"""SQLAlchemy models.

`import_all_models()` imports every model module so that Alembic autogenerate
and `Base.metadata` see the full schema. Add new model modules to the list.
"""

from __future__ import annotations

import importlib

_MODEL_MODULES: list[str] = [
    "app.models.user",
]


def import_all_models() -> None:
    for module in _MODEL_MODULES:
        importlib.import_module(module)
