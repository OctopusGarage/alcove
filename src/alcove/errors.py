from __future__ import annotations


class AlcoveError(Exception):
    """Base exception for expected Alcove failures."""


class WorkspaceNotFoundError(AlcoveError):
    """Raised when no .alcove workspace can be found."""


class AmbiguousIdError(AlcoveError):
    """Raised when an id prefix matches more than one object."""
