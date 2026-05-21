"""Ingest pipeline errors."""


class IngestError(Exception):
    """Base class for ingest failures."""


class IngestConfigError(IngestError):
    """Source is enabled but misconfigured (missing API key, empty config)."""
