import sys
from PyQt6.QtWidgets import QFileDialog

def get_dialog_options():
    """Returns standard options for file dialogs."""
    return QFileDialog.Option(0)

def get_existing_directory(parent, caption, directory=""):
    """Wrapper for QFileDialog.getExistingDirectory"""
    return QFileDialog.getExistingDirectory(
        parent, caption, directory,
        options=get_dialog_options()
    )

def get_open_file_name(parent, caption, directory="", filter=""):
    """Wrapper for QFileDialog.getOpenFileName"""
    return QFileDialog.getOpenFileName(
        parent, caption, directory, filter,
        options=get_dialog_options()
    )

def get_open_file_names(parent, caption, directory="", filter=""):
    """Wrapper for QFileDialog.getOpenFileNames"""
    return QFileDialog.getOpenFileNames(
        parent, caption, directory, filter,
        options=get_dialog_options()
    )

def get_save_file_name(parent, caption, directory="", filter=""):
    """Wrapper for QFileDialog.getSaveFileName"""
    return QFileDialog.getSaveFileName(
        parent, caption, directory, filter,
        options=get_dialog_options()
    )
