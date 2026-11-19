"""Building passage stage of ``build_plan`` (D18). Stub: passages are only reported as unsupported (the
wording the classifier used before routing) and buildings are not split; the feature task replaces the bodies."""

from .osm import _unsupported_reason
from .structures import report_unsupported


def build(plan, ctx):
    report_unsupported(ctx, getattr(ctx.classified, "passages", ()), _unsupported_reason)


def split(plan, ctx, feature):
    """The footprints to generate for building ``feature``: the stub returns it unchanged."""
    return [feature]
