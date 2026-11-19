"""Bridge stage of ``build_plan`` (D18). Stub: the in-area highway bridges are only reported as unsupported
(the wording the classifier used before routing); the feature task replaces the body."""

from .osm import _unsupported_reason
from .structures import report_unsupported


def build(plan, ctx):
    report_unsupported(ctx, getattr(ctx.classified, "structure_bridges", ()), _unsupported_reason)
