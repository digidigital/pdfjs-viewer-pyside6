"""Unsaved changes dialog for PDF viewer.

Provides a dialog to prompt users about unsaved annotations when:
- Closing the viewer
- Loading a new PDF
- Navigating away from the current document
"""

from PySide6.QtWidgets import QMessageBox
from .ui_translations import get_translations


class UnsavedChangesDialog(QMessageBox):
    """Dialog for unsaved annotation changes.

    Three options:
    - Save As: Choose filename and path with file picker
    - Save: Overwrite the original PDF with annotated version
    - Discard: Don't save, continue with navigation

    Example:
        dialog = UnsavedChangesDialog(parent_widget)
        result = dialog.get_result()
        if result == UnsavedChangesDialog.SAVE_AS:
            # Open file picker and save
        elif result == UnsavedChangesDialog.SAVE:
            # Overwrite original file
        else:  # DISCARD
            # Continue without saving
    """

    # Return values
    SAVE_AS = 0
    SAVE = 1
    DISCARD = 2

    def __init__(self, parent=None):
        """Initialize the unsaved changes dialog.

        Args:
            parent: Parent widget for the dialog.
        """
        super().__init__(parent)

        # Get translations for the current locale
        translations = get_translations()

        self.setWindowTitle(translations['unsaved_changes_title'])
        self.setText(translations['unsaved_changes_message'])
        self.setIcon(QMessageBox.Warning)

        # Add buttons (left to right: Save As, Save, Discard)
        self.save_as_btn = self.addButton(
            translations['button_save_as'],
            QMessageBox.AcceptRole
        )
        self.save_btn = self.addButton(
            translations['button_save'],
            QMessageBox.AcceptRole
        )
        self.discard_btn = self.addButton(
            translations['button_discard'],
            QMessageBox.DestructiveRole
        )

        # Set Save as the default button
        self.setDefaultButton(self.save_btn)

    def get_result(self) -> int:
        """Execute dialog and return the user's choice.

        Returns:
            One of SAVE_AS, SAVE, or DISCARD constants.
        """
        self.exec()
        clicked = self.clickedButton()
        if clicked == self.save_as_btn:
            return self.SAVE_AS
        elif clicked == self.save_btn:
            return self.SAVE
        else:
            return self.DISCARD
