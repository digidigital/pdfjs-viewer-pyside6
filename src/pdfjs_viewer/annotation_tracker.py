"""Qt-side annotation state tracking, independent of PDF.js internals.

This module provides reliable tracking of annotation modifications without
depending on PDF.js's internal state tracking mechanisms, which are complex
and may change between versions.
"""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Signal


class AnnotationStateTracker(QObject):
    """Tracks annotation modifications on the Qt side.

    This provides a reliable way to detect unsaved changes without
    depending on PDF.js's internal state tracking mechanisms.

    State is tracked via:
    1. JavaScript events forwarded through the bridge (annotation changes)
    2. Save operations that reset the modified flag
    3. PDF load operations that reset state entirely

    The tracker maintains:
    - Whether the current document has been modified
    - Count of modifications since last save
    - Timestamps for last modification and save

    Example:
        >>> tracker = AnnotationStateTracker()
        >>> tracker.set_document("doc_hash_123")
        >>> tracker.mark_modified()
        >>> tracker.has_unsaved_changes()
        True
        >>> tracker.mark_saved()
        >>> tracker.has_unsaved_changes()
        False
    """

    # Emitted when modification state changes
    state_changed = Signal(bool)  # True if now modified, False if saved/reset

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the annotation state tracker.

        Args:
            parent: Parent QObject (typically the backend).
        """
        super().__init__(parent)
        self._modified = False
        self._modification_count = 0
        self._last_modified_time: Optional[datetime] = None
        self._last_saved_time: Optional[datetime] = None
        self._current_document_id: Optional[str] = None

    def set_document(self, document_id: str):
        """Set current document identifier and reset state.

        Called when a new PDF is loaded. This resets all tracking state
        since we're now working with a fresh document.

        Args:
            document_id: Unique identifier for the document (e.g., file path hash
                        or a generated UUID for bytes-loaded documents).
        """
        self._current_document_id = document_id
        self._modified = False
        self._modification_count = 0
        self._last_modified_time = None
        # Don't reset _last_saved_time - it's useful to know when last save was
        self.state_changed.emit(False)

    def mark_modified(self):
        """Mark current document as having unsaved changes.

        Called when JavaScript reports annotation modifications via the bridge.
        This is idempotent for the modified flag but increments the counter.
        """
        was_modified = self._modified
        self._modified = True
        self._modification_count += 1
        self._last_modified_time = datetime.now()

        # Only emit if state actually changed
        if not was_modified:
            self.state_changed.emit(True)

    def mark_saved(self):
        """Mark current document as saved.

        Called after a successful save operation (either auto-save or Save As).
        Resets the modified flag but preserves the document identity.
        """
        was_modified = self._modified
        self._modified = False
        self._last_saved_time = datetime.now()
        # Don't reset modification_count - it tracks total changes, not unsaved ones

        # Only emit if state actually changed
        if was_modified:
            self.state_changed.emit(False)

    def has_unsaved_changes(self) -> bool:
        """Check if document has unsaved changes.

        This is the primary method used by handle_unsaved_changes() to
        determine whether to show a dialog or auto-save.

        Returns:
            True if there are unsaved changes, False otherwise.
        """
        return self._modified

    def reset(self):
        """Reset all tracking state.

        Called when:
        - Navigating away without saving (user chose to discard)
        - Closing the viewer
        - Loading a blank page

        This is different from set_document() which is for loading new PDFs.
        """
        self._modified = False
        self._modification_count = 0
        self._last_modified_time = None
        self._current_document_id = None
        self.state_changed.emit(False)

    @property
    def document_id(self) -> Optional[str]:
        """Current document identifier."""
        return self._current_document_id

    @property
    def modification_count(self) -> int:
        """Number of modifications since last load.

        This counts all modifications, not just unsaved ones. Useful for
        analytics or debugging.
        """
        return self._modification_count

    @property
    def last_modified(self) -> Optional[datetime]:
        """Time of last modification, or None if never modified."""
        return self._last_modified_time

    @property
    def last_saved(self) -> Optional[datetime]:
        """Time of last save, or None if never saved."""
        return self._last_saved_time

    @property
    def is_tracking(self) -> bool:
        """Whether we're currently tracking a document."""
        return self._current_document_id is not None
