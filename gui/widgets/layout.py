# ==============================================================================
# LAYOUT
# gui/widgets/layout.py
#
# Shared layout helpers (scrollable frame, header bars, table rows, hover
# highlighting) used across every tab — import from here rather than
# rebuilding these by hand in a tab file.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from gui.widgets.colors import (
    C_BG, C_DARK, C_GRAY, C_HDR, C_HEADER_BAR, C_HEADER_TEXT, C_HOVER, C_SELECTED, C_WHITE,
)
from gui.widgets.fonts import FONT_HEADER, FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY, FONT_TITLE

#make_table_header/make_data_row take character-count column widths (see
#gui/teams_tab/game_log.py's LOG_COLS) and convert them to CTkLabel pixel
#widths. 7px/char was tuned for FONT_SMALL_BOLD's old 9pt size; scaling it
#by how much that size has grown since keeps columns wide enough to avoid
#clipping text without needing to retune this constant by hand every time
#fonts.py's base sizes change.
_CHAR_PX = round(7 * FONT_SMALL_BOLD[1] / 9)


def create_scrollable_frame(
    parent: tk.Widget,
    bg: str = C_BG,
) -> tuple[ctk.CTkScrollableFrame, ctk.CTkScrollableFrame]:
    """
    Creates a vertically-scrollable area inside `parent`, using CTk's
    built-in CTkScrollableFrame (which owns its own internal canvas +
    scrollbar — no manual Canvas/Scrollbar wiring needed the way classic
    tkinter required).

    Returns
    -------
    (frame, frame) : the SAME CTkScrollableFrame instance twice, for
        backward compatibility with the old (canvas, inner) two-value
        return this replaced — add all scrollable content as children of
        either returned value. Call `.scroll_to_top()` on it (added below)
        instead of the old `canvas.yview_moveto(0)`.
    """
    frame = ctk.CTkScrollableFrame(parent, fg_color=bg)
    frame.pack(fill='both', expand=True)

    def _scroll_to_top() -> None:
        try:
            frame._parent_canvas.yview_moveto(0)
        except (AttributeError, tk.TclError):
            pass   #best-effort — CTkScrollableFrame's internal canvas is not public API

    frame.scroll_to_top = _scroll_to_top   #type: ignore[attr-defined]
    return frame, frame


def make_header_bar(
    parent: tk.Widget,
    title: str,
    subtitle: str = '',
    bg: str = C_HEADER_BAR,
) -> ctk.CTkFrame:
    """Dark header bar (full width) with a title on the left and optional
    subtitle on the right. Packed fill='x' into parent automatically.
    Always dark-navy-with-white-text regardless of theme (like the
    division title bars) — see C_HEADER_BAR/C_HEADER_TEXT's docstring in
    colors.py for why this uses fixed colors rather than C_DARK/C_WHITE."""
    bar = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    bar.pack(fill='x')
    ctk.CTkLabel(bar, text=title, fg_color=bg, text_color=C_HEADER_TEXT,
                font=FONT_HEADER).pack(side='left', padx=14, pady=7)
    if subtitle:
        ctk.CTkLabel(bar, text=subtitle, fg_color=bg, text_color=C_GRAY,
                    font=FONT_SMALL).pack(side='right', padx=14, pady=7)
    return bar


def make_table_header(
    parent: tk.Widget,
    columns: list[tuple[str, int, str]],  #(label, width, anchor)
    bg: str = C_HDR,
) -> ctk.CTkFrame:
    """One row of bold column-header labels for a data table."""
    row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    row.pack(fill='x', padx=2)
    for label, width, anchor in columns:
        ctk.CTkLabel(row, text=label, fg_color=bg, text_color=C_DARK,
                    font=FONT_SMALL_BOLD, width=width * _CHAR_PX, anchor=anchor,
                    padx=2).pack(side='left', pady=3)
    return row


def make_data_row(
    parent: tk.Widget,
    cells: list[tuple[str, int, str, str, bool]],  #(text, w, anchor, fg, bold)
    bg: str = C_WHITE,
    cursor: str = '',
    pady: int = 1,
) -> tuple[ctk.CTkFrame, list[ctk.CTkLabel]]:
    """
    Creates one data row packed into `parent`. corner_radius=0 throughout —
    these render by the hundred in a game log or player table, and flat
    rectangles are both the look the rest of the row-based tables use and
    cheaper to draw than CTk's default rounded corners at this volume.

    Returns
    -------
    row_frame : ctk.CTkFrame
    labels    : list[ctk.CTkLabel]  — same order as `cells`
    """
    row = ctk.CTkFrame(parent, fg_color=bg, cursor=cursor, corner_radius=0)
    row.pack(fill='x', padx=2, pady=pady)
    labels: list[ctk.CTkLabel] = []
    for text, width, anchor, fg, bold in cells:
        font = FONT_SMALL_BOLD if bold else FONT_SMALL
        lbl  = ctk.CTkLabel(row, text=text, fg_color=bg, text_color=fg,
                           font=font, width=width * _CHAR_PX, anchor=anchor, padx=2,
                           corner_radius=0)
        lbl.pack(side='left')
        labels.append(lbl)
    return row, labels


def make_stat_card(
    parent: tk.Widget,
    stats: list[tuple[str, str]],   #(label, value) — value on top
    bg: str = C_HEADER_BAR,
) -> ctk.CTkFrame:
    """Horizontal row of (value / label) boxes — used in team header cards
    and game detail popups. Always dark-navy-with-white-text regardless of
    theme — see C_HEADER_BAR/C_HEADER_TEXT's docstring in colors.py."""
    frame = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    frame.pack(side='right', padx=16)
    for label, value in stats:
        col = ctk.CTkFrame(frame, fg_color=bg, corner_radius=0)
        col.pack(side='left', padx=14)
        ctk.CTkLabel(col, text=value, fg_color=bg, text_color=C_HEADER_TEXT,
                    font=FONT_TITLE).pack()
        ctk.CTkLabel(col, text=label, fg_color=bg, text_color=C_GRAY,
                    font=FONT_TINY).pack()
    return frame


def set_row_bg(
    row: ctk.CTkFrame,
    labels: list[ctk.CTkLabel],
    bg: str,
) -> None:
    """Sets background on a row frame and all its child labels at once.
    Uses `.configure(fg_color=...)` — CTk widgets have no `bg` option, so
    the old tkinter `.config(bg=...)` call would raise on every one of
    these (hover highlight, row selection, etc.)."""
    row.configure(fg_color=bg)
    for lbl in labels:
        lbl.configure(fg_color=bg)


def bind_hover(
    row: ctk.CTkFrame,
    labels: list[ctk.CTkLabel],
    normal_bg: str,
    hover_bg: str = C_HOVER,
    *,
    skip_if_selected: bool = False,
    selected_bg: str = C_SELECTED,
) -> None:
    """Attaches mouse-enter/leave colour change to a row and its children.

    If skip_if_selected=True, hover does nothing when the row is currently
    showing selected_bg (so selection highlight doesn't flicker on hover)."""
    def on_enter(_: tk.Event) -> None:
        if skip_if_selected and row.cget('fg_color') == selected_bg:
            return
        set_row_bg(row, labels, hover_bg)

    def on_leave(_: tk.Event) -> None:
        if skip_if_selected and row.cget('fg_color') == selected_bg:
            return
        set_row_bg(row, labels, normal_bg)

    for widget in [row, *labels]:
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
