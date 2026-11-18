"""Error types. Every data-acquisition failure is surfaced, never papered over."""


class MapBuilderError(Exception):
    """Base error; ``str(err)`` is safe to show to users (no secrets)."""


class AreaError(MapBuilderError):
    """Requested area is invalid or exceeds configured bounds."""


class NetworkError(MapBuilderError):
    """Transport/HTTP failure."""

    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


class AuthError(NetworkError):
    """Provider rejected credentials (HTTP 401/403)."""


class CoverageError(MapBuilderError):
    """Provider/file has no data for (part of) the requested area."""


class NoDataError(CoverageError):
    """Raster contains NoData samples inside the requested area."""


class FormatError(MapBuilderError):
    """Input file is malformed or uses an unsupported variant."""


class LimitError(MapBuilderError):
    """A configured resource bound (bytes, vertices, objects...) was exceeded."""


class PackageError(MapBuilderError):
    """Map package failed validation."""
