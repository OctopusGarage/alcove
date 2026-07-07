from __future__ import annotations


class AlcoveError(Exception):
    """Base exception for expected Alcove failures."""


class WorkspaceNotFoundError(AlcoveError):
    """Raised when no .alcove workspace can be found."""


class WorkspaceInitializationError(AlcoveError):
    """Raised when a workspace cannot be initialized."""


class WorkspaceConfigError(AlcoveError):
    """Raised when a workspace config cannot be loaded."""


class TaxonomyError(AlcoveError):
    """Raised when a workspace taxonomy cannot be loaded."""


class AmbiguousIdError(AlcoveError):
    """Raised when an id prefix matches more than one object."""
