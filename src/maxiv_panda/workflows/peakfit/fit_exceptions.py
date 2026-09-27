"""Shared exceptions for the peak-fitting workflow."""


class FitCancelled(Exception):
    """Raised to interrupt an in-progress fit from the GUI."""
