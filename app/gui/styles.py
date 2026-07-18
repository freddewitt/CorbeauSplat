import json
from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.core.system import resolve_project_root

# Thèmes sombres disponibles. Chaque thème est un jeu de couleurs cohérent ;
# la structure de la feuille de style est commune (voir _STYLESHEET).
THEMES = {
    "slate": {  # Slate + Indigo
        "window": "#1a1b26", "surface": "#24283b", "base": "#16161e",
        "text": "#c0caf5", "muted": "#9aa5ce", "accent": "#7aa2f7",
        "border": "#2f3549", "btn": "#2a2f45", "btn_hover": "#343b5c",
        "btn_press": "#1f2335", "disabled": "#565f89",
        "highlight_text": "#1a1b26", "bright": "#f7768e",
    },
    "graphite": {  # Graphite + Teal
        "window": "#1e1e1e", "surface": "#2a2a2a", "base": "#181818",
        "text": "#e4e4e7", "muted": "#a1a1aa", "accent": "#2dd4bf",
        "border": "#3a3a3a", "btn": "#333333", "btn_hover": "#3f3f3f",
        "btn_press": "#262626", "disabled": "#6b7280",
        "highlight_text": "#0a0a0a", "bright": "#f87171",
    },
    "blue": {  # Bleu modernisé
        "window": "#1c2028", "surface": "#262b35", "base": "#12151a",
        "text": "#e5e9f0", "muted": "#9aa5b5", "accent": "#3b82f6",
        "border": "#333a47", "btn": "#2b313d", "btn_hover": "#353d4c",
        "btn_press": "#1a1e26", "disabled": "#5b6472",
        "highlight_text": "#ffffff", "bright": "#f87171",
    },
}

DEFAULT_THEME = "slate"

_STYLESHEET = Template("""
    QWidget { color: $text; }
    QToolTip {
        color: $text; background-color: $surface;
        border: 1px solid $border; border-radius: 6px; padding: 4px 6px;
    }
    QGroupBox {
        border: 1px solid $border; margin-top: 1.5em;
        border-radius: 8px; padding-top: 6px;
    }
    QGroupBox::title {
        subcontrol-origin: margin; subcontrol-position: top center;
        padding: 0 6px; color: $accent;
    }
    QTabWidget::pane { border: 1px solid $border; border-radius: 8px; top: -1px; }
    QTabBar::tab {
        background: transparent; color: $muted; padding: 7px 14px;
        border: 1px solid transparent;
        border-top-left-radius: 8px; border-top-right-radius: 8px;
        margin-right: 2px;
    }
    QTabBar::tab:hover { color: $text; background: $surface; }
    QTabBar::tab:selected {
        background: $surface; color: $accent;
        border: 1px solid $border; border-bottom-color: $surface;
    }
    QPushButton {
        background-color: $btn; border: 1px solid $border;
        border-radius: 8px; padding: 6px 14px; min-width: 80px;
    }
    QPushButton:hover { background-color: $btn_hover; border-color: $accent; }
    QPushButton:pressed { background-color: $btn_press; }
    QPushButton:disabled {
        background-color: $btn_press; border-color: $border; color: $disabled;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
        background-color: $base; border: 1px solid $border; border-radius: 8px;
        padding: 5px 8px; color: $text;
        selection-background-color: $accent; selection-color: $highlight_text;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
    QPlainTextEdit:focus, QTextEdit:focus { border: 1px solid $accent; }
    QComboBox::drop-down { border: none; width: 22px; }
    QComboBox QAbstractItemView {
        background-color: $base; border: 1px solid $border; border-radius: 8px;
        selection-background-color: $btn_hover; selection-color: $text; outline: none;
    }
    QProgressBar {
        border: 1px solid $border; border-radius: 8px; background-color: $base;
        text-align: center; color: $text; min-height: 16px;
    }
    QProgressBar::chunk { background-color: $accent; border-radius: 7px; }
    QCheckBox, QRadioButton, QLabel { color: $text; background: transparent; }
    QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
    QScrollBar::handle:vertical {
        background: $border; border-radius: 6px; min-height: 24px;
    }
    QScrollBar::handle:vertical:hover { background: $btn_hover; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
    QScrollBar::handle:horizontal {
        background: $border; border-radius: 6px; min-width: 24px;
    }
    QScrollBar::handle:horizontal:hover { background: $btn_hover; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
""")


def get_saved_theme():
    """Lit le thème enregistré dans config.json (défaut : slate)."""
    try:
        config_file = resolve_project_root() / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                name = json.load(f).get("theme", DEFAULT_THEME)
                if name in THEMES:
                    return name
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULT_THEME


def save_theme(name):
    """Enregistre le thème choisi dans config.json (préserve les autres clés)."""
    if name not in THEMES:
        return
    try:
        config_file = resolve_project_root() / "config.json"
        config = {}
        if config_file.exists():
            with open(config_file) as f:
                existing = json.load(f)
                if isinstance(existing, dict):
                    config = existing
        config["theme"] = name
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except (OSError, json.JSONDecodeError):
        pass


def set_dark_theme(app_instance=None, theme=None):
    """Applique un thème sombre. theme=None → thème enregistré dans config.json."""
    if app_instance is None:
        app_instance = QApplication.instance()
    if theme is None:
        theme = get_saved_theme()
    t = THEMES.get(theme, THEMES[DEFAULT_THEME])

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(t["window"]))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(t["base"]))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["surface"]))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["surface"]))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(t["surface"]))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(t["bright"]))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(t["accent"]))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["highlight_text"]))

    disabled = QColor(t["disabled"])
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)

    app_instance.setPalette(dark_palette)
    app_instance.setStyleSheet(_STYLESHEET.substitute(t))
