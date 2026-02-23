"""
🔧 Tool Executor (Facade)
Composes all mixin modules from the `executors` sub-package into a single
backward-compatible ``ToolExecutor`` class.

All method implementations live in the mixin modules under
``backend/chatbot/executors/``.  This file exists purely to preserve the
original import path::

    from .tool_executor import ToolExecutor
"""

from .executors.base import ExecutorBase
from .executors.normalizers import NormalizerMixin
from .executors.school_tools import SchoolToolsMixin
from .executors.count_tools import CountToolsMixin
from .executors.analysis_tools import AnalysisToolsMixin
from .executors.area_tools import AreaToolsMixin


class ToolExecutor(
    AnalysisToolsMixin,
    AreaToolsMixin,
    CountToolsMixin,
    SchoolToolsMixin,
    NormalizerMixin,
    ExecutorBase,
):
    """
    Executes education chatbot tools against Qdrant database.
    Each tool returns structured data that LLM can use to generate responses.

    This class is assembled via multiple inheritance (mixin pattern).
    ``ExecutorBase`` provides ``__init__``, ``execute()``, and Qdrant helpers.
    All other mixins provide the actual tool method implementations.
    """

    pass
