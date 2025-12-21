"""
GUI.components.styles - Theme and style configuration

Centralized theme constants for the entire GUI.
"""

from tkinter import ttk

# =====================================================================
# COLOR PALETTE - Dark Theme 2025
# =====================================================================

# Background colors
DARK_BG = "#121212"           # Main background
DARK_BG_ELEVATED = "#1E1E1E"  # Elevated surfaces (cards, modals)
DARK_BG_CARD = "#252525"      # Card backgrounds, input fields
DARK_BORDER = "#333333"       # Border color

# Text colors
TEXT_PRIMARY = "#F5F5F5"      # Primary text (white-ish)
TEXT_SECONDARY = "#B0B0B0"    # Secondary text (muted)
TEXT_DISABLED = "#666666"     # Disabled text

# Accent colors
ACCENT = "#00B894"            # Primary accent (teal/green)
ACCENT_SOFT = "#145A5A"       # Soft accent for backgrounds
ACCENT_HOVER = "#00CFA2"      # Hover state
ACCENT_ERROR = "#E74C3C"      # Error state (red)
ACCENT_WARNING = "#F39C12"    # Warning state (orange)
ACCENT_SUCCESS = "#27AE60"    # Success state (green)

# Sidebar
SIDEBAR_BG = "#0D0D0D"        # Sidebar background


# =====================================================================
# FONT CONFIGURATIONS
# =====================================================================

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

FONT_TITLE = (FONT_FAMILY, 12, "bold")
FONT_HEADER = (f"{FONT_FAMILY} Semibold", 14)
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_HINT = (FONT_FAMILY, 9, "italic")
FONT_MONO = (FONT_FAMILY_MONO, 9)


# =====================================================================
# STYLE INITIALIZATION
# =====================================================================

def init_dark_theme(style: ttk.Style = None) -> ttk.Style:
    """
    Initialize dark theme styles for ttk widgets.

    Args:
        style: Optional existing ttk.Style instance

    Returns:
        Configured ttk.Style instance
    """
    if style is None:
        style = ttk.Style()

    # Try to use clam theme as base
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # ==================== Frame styles ====================
    style.configure(
        "TFrame",
        background=DARK_BG,
    )

    style.configure(
        "Card.TFrame",
        background=DARK_BG_ELEVATED,
        relief="flat",
    )

    style.configure(
        "CardInner.TFrame",
        background=DARK_BG_CARD,
        relief="flat",
        borderwidth=1,
    )

    style.configure(
        "Sidebar.TFrame",
        background=SIDEBAR_BG,
    )

    # ==================== Label styles ====================
    style.configure(
        "TLabel",
        background=DARK_BG,
        foreground=TEXT_PRIMARY,
    )

    style.configure(
        "Title.TLabel",
        background=DARK_BG_ELEVATED,
        foreground=TEXT_PRIMARY,
        font=FONT_TITLE,
    )

    style.configure(
        "HeaderTitle.TLabel",
        background=SIDEBAR_BG,
        foreground=TEXT_PRIMARY,
        font=FONT_HEADER,
    )

    style.configure(
        "HeaderSub.TLabel",
        background=SIDEBAR_BG,
        foreground=TEXT_SECONDARY,
        font=FONT_SMALL,
    )

    style.configure(
        "LabelMuted.TLabel",
        foreground=TEXT_SECONDARY,
        background=DARK_BG_ELEVATED,
        font=FONT_SMALL,
    )

    style.configure(
        "LabelSub.TLabel",
        foreground=TEXT_SECONDARY,
        background=DARK_BG_ELEVATED,
        font=FONT_SMALL,
    )

    style.configure(
        "LabelHint.TLabel",
        foreground=TEXT_SECONDARY,
        background=DARK_BG_ELEVATED,
        font=FONT_HINT,
    )

    style.configure(
        "LabelError.TLabel",
        foreground=ACCENT_ERROR,
        background=DARK_BG_ELEVATED,
        font=FONT_SMALL,
    )

    style.configure(
        "LabelSuccess.TLabel",
        foreground=ACCENT_SUCCESS,
        background=DARK_BG_ELEVATED,
        font=FONT_SMALL,
    )

    # ==================== Button styles ====================
    style.configure(
        "TButton",
        background=DARK_BG_CARD,
        foreground=TEXT_PRIMARY,
        padding=(8, 4),
    )
    style.map(
        "TButton",
        background=[("active", "#2C2C2C")],
    )

    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#FFFFFF",
        font=(FONT_FAMILY, 9, "bold"),
        padding=(10, 4),
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_HOVER)],
    )

    style.configure(
        "SidebarButton.TButton",
        background=SIDEBAR_BG,
        foreground=TEXT_SECONDARY,
        padding=8,
        relief="flat",
        borderwidth=0,
        anchor="w",
    )
    style.map(
        "SidebarButton.TButton",
        background=[("active", "#151515"), ("selected", "#1F1F1F")],
        foreground=[("active", TEXT_PRIMARY)],
    )

    style.configure(
        "SidebarButtonActive.TButton",
        background=ACCENT_SOFT,
        foreground=TEXT_PRIMARY,
    )

    style.configure(
        "Danger.TButton",
        background=ACCENT_ERROR,
        foreground="#FFFFFF",
        padding=(10, 4),
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#C0392B")],
    )

    # ==================== Entry styles ====================
    style.configure(
        "TEntry",
        fieldbackground=DARK_BG_CARD,
        foreground=TEXT_PRIMARY,
        insertcolor=ACCENT,
        borderwidth=0,
    )

    # ==================== Combobox styles ====================
    style.configure(
        "TCombobox",
        fieldbackground=DARK_BG_CARD,
        foreground=TEXT_PRIMARY,
        background=DARK_BG_CARD,
    )

    # ==================== Progressbar styles ====================
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=DARK_BG_CARD,
        background=ACCENT,
        bordercolor=DARK_BG_CARD,
        lightcolor=ACCENT,
        darkcolor=ACCENT_SOFT,
    )

    # ==================== Checkbutton styles ====================
    style.configure(
        "TCheckbutton",
        background=DARK_BG_ELEVATED,
        foreground=TEXT_PRIMARY,
    )
    style.map(
        "TCheckbutton",
        background=[("active", DARK_BG_CARD)],
    )

    # ==================== Radiobutton styles ====================
    style.configure(
        "TRadiobutton",
        background=DARK_BG_ELEVATED,
        foreground=TEXT_PRIMARY,
    )
    style.map(
        "TRadiobutton",
        background=[("active", DARK_BG_CARD)],
    )

    # ==================== Notebook styles ====================
    style.configure(
        "TNotebook",
        background=DARK_BG,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=DARK_BG_CARD,
        foreground=TEXT_SECONDARY,
        padding=(12, 6),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", DARK_BG_ELEVATED)],
        foreground=[("selected", TEXT_PRIMARY)],
    )

    # ==================== Scrollbar styles ====================
    style.configure(
        "TScrollbar",
        background=DARK_BG_CARD,
        troughcolor=DARK_BG_ELEVATED,
        bordercolor=DARK_BG,
        arrowcolor=TEXT_SECONDARY,
    )

    # ==================== Separator styles ====================
    style.configure(
        "TSeparator",
        background=DARK_BORDER,
    )

    return style


def get_listbox_config() -> dict:
    """
    Get configuration dict for tk.Listbox with dark theme.

    Returns:
        Dict of configuration options
    """
    return {
        "bg": DARK_BG_CARD,
        "fg": TEXT_PRIMARY,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 0,
        "selectbackground": ACCENT_SOFT,
        "selectforeground": TEXT_PRIMARY,
    }


def get_text_config() -> dict:
    """
    Get configuration dict for tk.Text with dark theme.

    Returns:
        Dict of configuration options
    """
    return {
        "bg": DARK_BG_CARD,
        "fg": TEXT_PRIMARY,
        "insertbackground": ACCENT,
        "relief": "flat",
        "bd": 0,
        "wrap": "word",
        "font": FONT_MONO,
    }
