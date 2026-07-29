# ==============================================================================
# SORTABLE TABLE
# gui/widgets/table.py
#
# A reusable ttk.Treeview with sort + search + filter, used by every tab
# that shows tabular data (standings, stats, team lists, players). Stays
# ttk.Treeview on purpose — no CTk equivalent exists for a data table at
# this scale (the Player Tab can run into hundreds of rows).
# ==============================================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, NamedTuple, Optional

import customtkinter as ctk

from gui.widgets.colors import C_BG, C_DARK, C_HDR, C_PANEL, C_ROW_ALT, C_SELECTED, C_WHITE
from gui.widgets.fonts import FONT_SMALL, FONT_SMALL_BOLD

#Base (100% DPI) size for the Treeview body text and heading text/row
#height. These are deliberately larger than FONT_SMALL's raw (9pt) size —
#ttk.Treeview is the one widget class in the whole app that customtkinter
#does NOT scale automatically (see dpi_scale() below), so it needs its
#own comfortably-readable baseline rather than inheriting the small size
#meant for compact CTk labels.
_TREE_BASE_FONT_SIZE = 12
_TREE_BASE_ROWHEIGHT = 30
_TREE_HEADING_BASE_FONT_SIZE = 12

#Every caller's Column(width=...) pixel values (and SortableTable's own
#name_col_w default) were hand-tuned against the OLD 9pt Treeview font.
#Now that the body font is bigger, the same pixel width fits fewer
#characters — without a correction, text that used to fit now gets cut
#off ("Milwaukee Brewers" -> "Milwaukee Brev", "Rating" -> "Ratin"). Since
#there are many callers with their own hand-picked widths, the column
#widths are scaled centrally, here, by how much the font grew, rather
#than requiring every caller to redo its numbers.
_OLD_BASE_FONT_SIZE = 9


def dpi_scale(widget: tk.Widget) -> float:
    """
    Returns the DPI/user scaling factor CTk is currently applying to its
    own widgets (CTkLabel, CTkButton, etc.) for the monitor `widget` is on.

    Every CTk widget auto-scales for high-DPI displays via customtkinter's
    ScalingTracker — that's why the nav bar, buttons, and entry boxes look
    correctly sized in a screenshot. ttk.Treeview is a plain Tk/ttk widget,
    so it's invisible to that system and stays at its literal point size
    while everything else around it gets scaled up, which is what makes
    table text look "way too small" next to the rest of the UI on a scaled
    display. Multiplying our own font/rowheight numbers by this same
    factor keeps the Treeview visually consistent with the CTk widgets
    surrounding it.

    Falls back to 1.0 (no scaling) if the tracker isn't available for any
    reason — e.g. the widget isn't attached to a root window yet — so a
    lookup failure here degrades to "unscaled," never a crash.
    """
    try:
        return float(ctk.ScalingTracker.get_widget_scaling(widget))
    except Exception:
        return 1.0


class Column(NamedTuple):
    """One column definition for SortableTable.

    col_id   : stable id
    header   : column title (a sort-direction arrow is appended when active)
    width    : pixel width (0 = stretch/measured at runtime)
    anchor   : 'w' | 'e' | 'center' — right-justify ('e') for numerics
    sort_key : row_dict -> comparable, or None for a non-sortable column
    display  : row_dict -> str shown in the cell
    """
    col_id:   str
    header:   str
    width:    int
    anchor:   str
    sort_key: Optional[Callable[[dict], Any]]
    display:  Callable[[dict], str]


class SortableTable(ctk.CTkFrame):
    """A reusable data table built on ttk.Treeview.

    Features
    --------
    - Click a column header to sort; click again to flip direction. Numeric
      columns sort on the RAW value returned by `sort_key`, not the string.
    - Optional search box: live-filters rows by `search_key` (default 'team').
    - Optional filter dropdown (e.g. league/division) driven by `filter_key`.
    - Zebra striping, bold headers, right-justified numeric columns, and a
      '#' rank column that renumbers to match the current sort/filter.
    - Ctrl+C copies the currently-visible rows as an aligned text table.

    Data model
    ----------
    `rows` is a list of dicts. Each column's `display`/`sort_key` receives the
    row dict (augmented with '_rank'). Nothing here recomputes stats — callers
    pass fully-derived rows so this stays a pure view.
    """

    def __init__(
        self,
        parent:        tk.Widget,
        columns:       list[Column],
        rows:          list[dict],
        *,
        default_sort:  Optional[str] = None,
        default_asc:   bool = False,
        search_key:    Optional[str] = None,
        show_search:   bool = False,
        filter_key:    Optional[str] = None,
        filter_values: Optional[list[str]] = None,
        filter_label:  str = 'Filter',
        name_col_w:    int = 150,
        style_name:    str = 'Sortable.Treeview',
        row_image:     Optional[Callable[[dict], Optional[tk.PhotoImage]]] = None,
    ) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._columns     = columns
        self._rows        = rows
        self._sort_col    = default_sort or (columns[0].col_id if columns else '')
        self._sort_asc    = default_asc
        self._search_key  = search_key or 'team'
        self._show_search = show_search
        self._filter_key  = filter_key
        self._filter_val  = 'All'
        self._name_col_w  = name_col_w
        self._style_name  = style_name
        self._row_image   = row_image

        self._search_var = tk.StringVar()
        self._filter_var = tk.StringVar(value='All')
        self._filter_values = ['All'] + list(filter_values or [])
        self._filter_label = filter_label
        self._tree: ttk.Treeview | None = None
        self._build()

    #── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        if self._show_search or self._filter_key:
            self._build_controls()

        scale = dpi_scale(self)
        body_font = ('Inter', round(_TREE_BASE_FONT_SIZE * scale))
        heading_font = ('Inter', round(_TREE_HEADING_BASE_FONT_SIZE * scale), 'bold')
        rowheight = round(_TREE_BASE_ROWHEIGHT * scale)

        sty = ttk.Style()
        #'clam' is used instead of the platform default theme (e.g.
        #'vista'/'winnative' on Windows) because those themes ignore
        #several Treeview style overrides (rowheight in particular, and
        #sometimes fieldbackground) — 'clam' honors them consistently
        #across platforms, which matters now that rowheight/font are
        #computed dynamically rather than left at Tk's built-in default.
        sty.theme_use('clam')
        sty.configure(self._style_name,
                      font=body_font, rowheight=rowheight,
                      background=C_WHITE, fieldbackground=C_WHITE,
                      foreground=C_DARK, borderwidth=0)
        sty.configure(f'{self._style_name}.Heading',
                      font=heading_font, background=C_HDR,
                      foreground=C_DARK, relief='flat', padding=(4, 6))
        sty.map(self._style_name, background=[('selected', C_SELECTED)])

        tree_frame = ctk.CTkFrame(self, fg_color=C_WHITE, corner_radius=0)
        tree_frame.pack(fill='both', expand=True)

        col_ids = [c.col_id for c in self._columns]
        show = 'tree headings' if self._row_image else 'headings'
        tree = ttk.Treeview(tree_frame, style=self._style_name,
                            columns=col_ids, show=show,
                            selectmode='browse')
        if self._row_image:
            #the '#0' tree column is normally hidden by show='headings'; reserving it as a
            #narrow icon-only column is the only place ttk.Treeview will actually render a
            #per-row image — there's no way to put one inside a regular data column
            icon_w = round(28 * scale)
            tree.column('#0', width=icon_w, minwidth=icon_w, stretch=False, anchor='center')
            tree.heading('#0', text='')
        width_scale = (_TREE_BASE_FONT_SIZE / _OLD_BASE_FONT_SIZE) * scale
        for c in self._columns:
            w = round((self._name_col_w if c.width == 0 else c.width) * width_scale)
            stretch = (c.width == 0)
            tree.column(c.col_id, width=w, minwidth=w if stretch else 30,
                        anchor=c.anchor, stretch=stretch)
            tree.heading(c.col_id, text=c.header,
                         command=lambda k=c.col_id: self._on_sort(k))

        tree.tag_configure('alt', background=C_ROW_ALT)

        sty.configure('Sortable.Vertical.TScrollbar',
                      background=C_HDR, troughcolor=C_WHITE,
                      bordercolor=C_WHITE, arrowcolor=C_DARK, relief='flat')
        sb = ttk.Scrollbar(tree_frame, orient='vertical',
                           style='Sortable.Vertical.TScrollbar', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self._tree = tree
        self._update_headers()
        self._refresh()

        tree.bind('<Control-c>', lambda _e: self._copy_to_clipboard())

    def _build_controls(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0)
        bar.pack(fill='x')
        if self._show_search:
            ctk.CTkLabel(bar, text='Search:', fg_color=C_PANEL, text_color=C_DARK,
                        font=FONT_SMALL_BOLD).pack(side='left', padx=(10, 4), pady=4)
            entry = ctk.CTkEntry(bar, textvariable=self._search_var,
                                width=130, font=FONT_SMALL)
            entry.pack(side='left', padx=(0, 12), pady=4)
            self._search_var.trace_add('write', lambda *_: self._refresh())
        if self._filter_key:
            ctk.CTkLabel(bar, text=f'{self._filter_label}:', fg_color=C_PANEL, text_color=C_DARK,
                        font=FONT_SMALL_BOLD).pack(side='left', padx=(4, 4), pady=4)
            om = ctk.CTkOptionMenu(bar, variable=self._filter_var, values=self._filter_values,
                                  font=FONT_SMALL, command=lambda _v: self._refresh())
            om.pack(side='left', padx=(0, 10), pady=4)

    #── sort ──────────────────────────────────────────────────────────────────

    def _on_sort(self, col_id: str) -> None:
        col = self._col(col_id)
        if col is None or col.sort_key is None:
            return
        if self._sort_col == col_id:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col_id
            self._sort_asc = False   #numerics default high-to-low
        self._update_headers()
        self._refresh()

    def _col(self, col_id: str) -> Optional[Column]:
        for c in self._columns:
            if c.col_id == col_id:
                return c
        return None

    def _update_headers(self) -> None:
        arrow = ' ▲' if self._sort_asc else ' ▼'
        for c in self._columns:
            text = (c.header + arrow) if c.col_id == self._sort_col else c.header
            self._tree.heading(c.col_id, text=text)

    #── filtering + rendering ───────────────────────────────────────────────────

    def _visible_rows(self) -> list[dict]:
        rows = list(self._rows)

        fval = self._filter_var.get()
        if self._filter_key and fval and fval != 'All':
            rows = [r for r in rows if str(r.get(self._filter_key, '')) == fval]

        q = self._search_var.get().strip().lower()
        if q:
            rows = [r for r in rows
                    if q in str(r.get(self._search_key, '')).lower()]

        col = self._col(self._sort_col)
        if col and col.sort_key is not None:
            rows.sort(key=lambda r: col.sort_key(r), reverse=not self._sort_asc)
        return rows

    def _refresh(self) -> None:
        tree = self._tree
        if tree is None:
            return
        tree.delete(*tree.get_children())
        for rank, row in enumerate(self._visible_rows(), 1):
            r = dict(row)
            r['_rank'] = rank
            values = [c.display(r) for c in self._columns]
            tag = ('alt',) if rank % 2 == 0 else ()
            #get_team_logo() (gui/logos/loader.py) already caches every PhotoImage at module
            #level for the app's lifetime, so there's no extra Tkinter GC ref needed here —
            #unlike a one-off tk.Label(image=...), a Treeview row doesn't hold its own reference
            image = self._row_image(r) if self._row_image else ''
            tree.insert('', 'end', values=values, tags=tag, image=image or '')

    def set_rows(self, rows: list[dict]) -> None:
        """Replace the backing data and re-render (keeps sort/search/filter)."""
        self._rows = rows
        self._refresh()

    #── copy ──────────────────────────────────────────────────────────────────

    def _copy_to_clipboard(self) -> None:
        headers = [c.header for c in self._columns]
        widths = [max(len(h), 6) for h in headers]
        rows: list[list[str]] = []
        for iid in self._tree.get_children():
            vals = [str(v) for v in self._tree.item(iid, 'values')]
            rows.append(vals)
            for i, v in enumerate(vals):
                widths[i] = max(widths[i], len(v))

        lines = [' '.join(h.ljust(widths[i]) for i, h in enumerate(headers)),
                 '-' * (sum(widths) + len(widths))]
        for row in rows:
            lines.append(' '.join(v.ljust(widths[i]) for i, v in enumerate(row)))
        self.clipboard_clear()
        self.clipboard_append('\n'.join(lines))
