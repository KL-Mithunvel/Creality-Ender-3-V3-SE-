"""Exception types shared across the package.

Simulated and real links raise the *same* types so callers cannot tell them apart
(CLAUDE-COMMON rule 2).
"""

from __future__ import annotations


class MagnetEmbedError(Exception):
    """Base class for every error this package raises."""


# --- printer link ---------------------------------------------------------

class PrinterConnectionError(MagnetEmbedError):
    """Could not open or handshake with the printer."""


class AckTimeout(MagnetEmbedError):
    """The printer did not return `ok` within the timeout, and was not busy/waiting."""


class PrinterError(MagnetEmbedError):
    """The firmware reported an `Error:` line."""


class ResendRequested(MagnetEmbedError):
    """The firmware asked for a line resend.

    We stream plain lines (no N-numbers / checksums), so we cannot satisfy this and
    treat it as fatal for the run. See `project/BUILD_PLAN.md` -> protocol notes.
    """

    def __init__(self, line_number: int, message: str = ""):
        self.line_number = line_number
        super().__init__(message or f"firmware requested resend from line {line_number}")


# --- gcode / sentinel ----------------------------------------------------

class SentinelParseError(MagnetEmbedError):
    """A line began with the sentinel token but its fields were missing / malformed."""


class SentinelNotFound(MagnetEmbedError):
    """`require_sentinel` was set but EOF was reached without seeing one."""


# --- dispenser ---------------------------------------------------------

class DispenserError(MagnetEmbedError):
    """The dispenser MCU reported `ERR ...`, or failed to respond."""


# --- insert sequence -------------------------------------------------

class OutOfEnvelopeError(MagnetEmbedError):
    """A computed move target lies outside the machine limits."""


class SequenceAborted(MagnetEmbedError):
    """The operator chose Abort at the insert prompt."""
