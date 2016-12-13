﻿"""Define the Table class."""


import warnings
from typing import List, Match, Union, Optional, TypeVar

import regex

from .tag import attrs_parser, ATTRS_REGEX, SubWikiTextWithAttrs
from .cell import (
    Cell,
    NEWLINE_CELL_REGEX,
    INLINE_HAEDER_CELL_REGEX,
    INLINE_NONHAEDER_CELL_REGEX
)


CAPTION_REGEX = regex.compile(
    r"""
    # Everything until the caption line
    (?P<preattrs>
        # Start of table
        {\|
        (?:
            (?:
                (?!\n\s*\|)
                [\s\S]
            )*?
        )
        # Start of caption line
        \n\s*\|\+
    )
    # Optional caption attrs
    (?:
        (?P<attrs>[^\n|]*)
        (?:\|)
        (?!\|)
    )?
    (?P<caption>.*?)
    # End of caption line
    (?:
        \n|
        \|\|
    )
    """,
    regex.VERBOSE
)
T = TypeVar('T')


class Table(SubWikiTextWithAttrs):

    """Create a new Table object."""
    # Todo: Define has, get, set, and delete methods.
    # They should provide the same API as in Tag and Cell classes.

    @property
    def _match_table(self) -> List[List[Match]]:
        """Return match_table."""
        shadow = self._shadow
        # Remove table-start and table-end marks.
        pos = shadow.find('\n')
        lsp = _lstrip_increase(shadow, pos)
        # Remove everything until the first row
        while shadow[lsp] not in '!|':
            nlp = shadow.find('\n', lsp)
            pos = nlp
            lsp = _lstrip_increase(shadow, pos)
        # Start of the first row
        match_table = []
        pos = _semi_caption_increase(shadow, pos)
        rsp = _row_separator_increase(shadow, pos)
        pos = -1
        while pos != rsp:
            pos = rsp
            # We have a new row.
            m = NEWLINE_CELL_REGEX.match(shadow, pos)
            # Don't add a row if there are no new cells.
            if m:
                match_row = []
                match_table.append(match_row)
            while m:
                match_row.append(m)
                sep = m.group('sep')
                pos = m.end()
                if sep == '|':
                    m = INLINE_NONHAEDER_CELL_REGEX.match(shadow, pos)
                    while m:
                        match_row.append(m)
                        pos = m.end()
                        m = INLINE_NONHAEDER_CELL_REGEX.match(shadow, pos)
                elif sep == '!':
                    m = INLINE_HAEDER_CELL_REGEX.match(shadow, pos)
                    while m:
                        match_row.append(m)
                        pos = m.end()
                        m = INLINE_HAEDER_CELL_REGEX.match(shadow, pos)
                pos = _semi_caption_increase(shadow, pos)
                m = NEWLINE_CELL_REGEX.match(shadow, pos)
            rsp = _row_separator_increase(shadow, pos)
        return match_table

    def getdata(self, span: bool=True) -> List[List[str]]:
        """Use Table.data instead."""
        warnings.warn(
            'Table.getdata is deprecated. Use Table.data instead.',
            DeprecationWarning,
        )
        return self.data(span)

    def data(
        self, span: bool=True,
        strip: bool= True,
        row: int=None,
        column: int=None
    ) -> Union[List[List[str]], List[str], str]:
        """Return a list containing lists of row values.

        :span: If true, calculate rows according to rowspans and colspans
            attributes. Otherwise ignore them.
        :row: Return the specified row only. Zero-based index.
        :column: Return the specified column only. Zero-based index.

        Note: Due to the lots of complications that it may cause, this function
            won't look inside templates, parser functions, etc.
            See https://www.mediawiki.org/wiki/Extension:Pipe_Escape for how
            wikitables can be inserted within templates.

        """
        match_table = self._match_table
        string = self.string
        table_data = []
        if strip:
            for match_row in match_table:
                row_data = []
                table_data.append(row_data)
                for m in match_row:
                    # Spaces after the first newline can be meaningful
                    s, e = m.span('data')
                    row_data.append(string[s:e].lstrip(' ').rstrip())
        else:
            for match_row in match_table:
                row_data = []
                table_data.append(row_data)
                for m in match_row:
                    s, e = m.span('data')
                    row_data.append(string[s:e])
        if table_data:
            if span:
                table_attrs = []
                for match_row in match_table:
                    row_attrs = []
                    table_attrs.append(row_attrs)
                    for m in match_row:
                        s, e = m.span('attrs')
                        row_attrs.append(attrs_parser(string, s, e))
                table_data = _apply_attr_spans(table_attrs, table_data)
        if row is None:
            if column is None:
                return table_data
            return [r[column] for r in table_data]
        if column is None:
            return table_data[row]
        return table_data[row][column]

    def cells(
        self, row: int=None, column: int=None, span: bool=True,
    ) -> Union[List[List[Cell]], List[Cell], Cell]:
        """Return a list of lists containing Cell objects.

        :span: If is True, rearrange the result according to colspan and rospan
            attributes.
        :row: Return the specified row only. Zero-based index.
        :column: Return the specified column only. Zero-based index.

        If both row and column are provided, return the relevant cell object.

        If only need the values inside cells, then use the ``data`` method
        instead.

        """
        ss = self._span[0]
        match_table = self._match_table
        # todo: maybe shadow is better than string? add tests.
        string = self.string
        type_ = 'tc' + str(self._index)
        type_to_spans = self._type_to_spans
        if type_ not in type_to_spans:
            type_to_spans[type_] = []
        spans = type_to_spans[type_]
        table_cells = []
        table_attrs = []
        attrs_match = None
        for match_row in match_table:
            row_cells = []
            table_cells.append(row_cells)
            header = match_row[0].group('sep') == '!'
            if span:
                row_attrs = []
                table_attrs.append(row_attrs)
                row_attrs_append = row_attrs.append
            for m in match_row:
                if span:
                    s, e = m.span('attrs')
                    # NOte: ATTRS_REGEX always matches, even to empty strings.
                    attrs_match = ATTRS_REGEX.match(string, s, e)
                    captures = attrs_match.captures
                    row_attrs_append(dict(zip(
                        captures('attr_name'), captures('attr_value')
                    )))
                ms, me = m.span()
                cell_span = (ss + ms, ss + me)
                index = next(
                    (i for i, s in enumerate(spans) if s == cell_span),
                    None
                )
                if index is None:
                    index = len(spans)
                    spans.append(cell_span)
                row_cells.append(
                    Cell(
                        self._lststr,
                        header,
                        type_to_spans,
                        index,
                        type_,
                        m,
                        attrs_match,
                    )
                )
        if table_cells and span:
            table_cells = _apply_attr_spans(table_attrs, table_cells)
        if row is None:
            if column is None:
                return table_cells
            return [r[column] for r in table_cells]
        if column is None:
            return table_cells[row]
        return table_cells[row][column]

    def getrdata(self, i: int, span: bool=True) -> List[str]:
        """Use Table.data(span, row=i) instead."""
        warnings.warn(
            'Table.getrdata is deprecated. Use data(span, row=i) instead.',
            DeprecationWarning,
        )
        return self.data(span, row=i)

    def getcdata(self, i: int, span: bool=True) -> List[str]:
        """Use Table.data(span, column=i) instead."""
        warnings.warn(
            'Table.getcdata is deprecated. Use data(span, column=i) instead.',
            DeprecationWarning,
        )
        return self.data(span, column=i)

    @property
    def caption(self) -> Optional[str]:
        """Return caption of the table."""
        m = CAPTION_REGEX.match(self.string)
        if m:
            return m.group('caption')

    @caption.setter
    def caption(self, newcaption: str) -> None:
        """Set a new caption."""
        m = CAPTION_REGEX.match(self.string)
        if m:
            preattrs = m.group('preattrs')
            attrs = m.group('attrs') or ''
            oldcaption = m.group('caption')
            self[len(preattrs + attrs):len(preattrs + attrs + oldcaption)] =\
                newcaption
        else:
            # There is no caption. Create one.
            string = self.string
            h, s, t = string.partition('\n')
            # Insert caption after the first one.
            self.insert(len(h + s), '|+' + newcaption + '\n')

    @property
    def _attrs_match(self) -> Match:
        shadow = self._shadow
        cache = getattr(self, '_cached_attrs_match', None)
        if cache and cache.string == shadow:
            return cache
        attrs_match = ATTRS_REGEX.match(shadow, 2, shadow.find('\n'))
        self._cached_attrs_match = attrs_match
        return attrs_match

    @property
    def table_attrs(self) -> str:
        """Return table attributes.

        Placing attributes after the table start tag ({|) applies
        attributes to the entire table.
        See [[mw:Help:Tables#Attributes on tables]] for more info.

        """
        # Todo: Use attrs, get, set, etc. and deprecate this function
        return self.string.partition('\n')[0][2:]

    @table_attrs.setter
    def table_attrs(self, attrs: str) -> None:
        """Set new attributes for this table."""
        h = self.string.partition('\n')[0]
        self[2:2 + len(h[2:])] = attrs

    @property
    def caption_attrs(self) -> Optional[str]:
        """Return caption attributes."""
        m = CAPTION_REGEX.match(self.string)
        if m:
            return m.group('attrs')

    @caption_attrs.setter
    def caption_attrs(self, attrs: str) -> None:
        """Set new caption attributes."""
        string = self.string
        h, s, t = string.partition('\n')
        m = CAPTION_REGEX.match(string)
        if not m:
            # There is no caption-line
            self.insert(len(h + s), '|+' + attrs + '|\n')
        else:
            preattrs = m.group('preattrs')
            oldattrs = m.group('attrs') or ''
            # Caption and attrs or Caption but no attrs
            self[len(preattrs):len(preattrs + oldattrs)] = attrs


def _apply_attr_spans(
    table_attrs: List[List[Match]], table_data: List[List[T]]
) -> List[List[T]]:
    """Apply row and column spans and return table_data."""
    # The following code is based on the table forming algorithm described
    # at http://www.w3.org/TR/html5/tabular-data.html#processing-model-1
    # Numbered comments indicate the step in that algorithm.
    # 1
    xwidth = 0
    # 2
    yheight = 0
    # 4
    # The xwidth and yheight variables give the table's dimensions.
    # The table is initially empty.
    table = []
    # Table.data won't call this function if table_data is empty.
    # 5
    # if not table_data:
    #     return table_data
    # 10
    ycurrent = 0
    # 11
    downward_growing_cells = []
    # 13, 18
    # Algorithm for processing rows
    for i, row in enumerate(table_data):
        # 13.1 ycurrent is never greater than yheight
        if yheight == ycurrent:
            yheight += 1
            table.append([None] * xwidth)
        # 13.2
        xcurrent = 0
        # 13.3
        # The algorithm for growing downward-growing cells
        for cell, cellx, width in downward_growing_cells:
            r = table[ycurrent]
            for x in range(cellx, cellx + width):
                r[x] = cell
        # 13.4 will be handled by the following for-loop.
        # 13.5, 13.16
        for j, current_cell in enumerate(row):
            # 13.6
            while (
                xcurrent < xwidth and
                table[ycurrent][xcurrent] is not None
            ):
                xcurrent += 1
            # 13.7
            if xcurrent == xwidth:
                # xcurrent is never greater than xwidth
                xwidth += 1
                for r in table:
                    if xwidth > len(r):
                        r.extend([None] * (xwidth - len(r)))
            # 13.8
            colspan = int(table_attrs[i][j].get('colspan', 1))
            if colspan == 0:
                # Note: colspan="0" tells the browser to span the cell to
                # the last column of the column group (colgroup)
                # http://www.w3schools.com/TAGS/att_td_colspan.asp
                colspan = 1
            # 13.9
            rowspan = int(table_attrs[i][j].get('rowspan', 1))
            # 13.10
            if rowspan == 0:
                # Note: rowspan="0" tells the browser to span the cell to the
                # last row of the table.
                # http://www.w3schools.com/tags/att_td_rowspan.asp
                cell_grows_downward = True
                rowspan = 1
            else:
                cell_grows_downward = False
            # 13.11
            if xwidth < xcurrent + colspan:
                xwidth = xcurrent + colspan
                for r in table:
                    if xwidth > len(r):
                        r.extend([None] * (xwidth - len(r)))
            # 13.12
            if yheight < ycurrent + rowspan:
                yheight = ycurrent + rowspan
                while len(table) < yheight:
                    table.append([None] * xwidth)
            # 13.13
            for y in range(ycurrent, ycurrent + rowspan):
                r = table[y]
                for x in range(xcurrent, xcurrent + colspan):
                    # If any of the slots involved already had a cell
                    # covering them, then this is a table model error.
                    # Those slots now have two cells overlapping.
                    r[x] = current_cell
                    # Skipping algorithm for assigning header cells
            # 13.14
            if cell_grows_downward:
                downward_growing_cells.append(
                    (current_cell, xcurrent, colspan)
                )
            # 13.15
            xcurrent += colspan
        # 13.16
        ycurrent += 1
    # 14
    # The algorithm for ending a row group
    # 14.1
    while ycurrent < yheight:
        # 14.1.1
        # Run the algorithm for growing downward-growing cells.
        for cell, cellx, width in downward_growing_cells:
            for x in range(cellx, cellx + width):
                table[ycurrent][x] = cell
        # 14.2.2
        ycurrent += 1
    # 14.2
    # downward_growing_cells = []
    # 20 If there exists a row or column in the table containing only
    # slots that do not have a cell anchored to them,
    # then this is a table model error.
    return table


def _lstrip_increase(string: str, pos: int) -> int:
    """Return the new position to lstrip the string."""
    length = len(string)
    while pos < length and string[pos].isspace():
        pos += 1
    return pos


def _semi_caption_increase(string: str, pos: int) -> int:
    """Return the position after the starting semi-caption.

    Captions are optional and only one should be placed between table-start
    and the first row. Others captions are not part of the table and will
    be ignored. We call these semi-captions.

    """
    lsp = _lstrip_increase(string, pos)
    while string.startswith('|+', lsp):
        pos = string.find('\n', lsp + 2)
        lsp = _lstrip_increase(string, pos)
        while string[lsp] not in ('!', '|'):
            # This line is a continuation of semi-caption line.
            nlp = string.find('\n', lsp + 1)
            if nlp == -1:
                # This is the last line that ends with '|}'.
                return pos
            pos = nlp
            lsp = _lstrip_increase(string, nlp)
    return pos


def _row_separator_increase(string: str, pos: int) -> int:
    """Return the position after the starting row separator line.

    Also skips any semi-caption lines before and after the separator.

    """
    # General format of row separators: r'\|-[^\n]*\n'
    scp = _semi_caption_increase(string, pos)
    lsp = _lstrip_increase(string, scp)
    while string.startswith('|-', lsp):
        # We are on a row separator line.
        pos = string.find('\n', lsp + 2)
        pos = _semi_caption_increase(string, pos)
        lsp = _lstrip_increase(string, pos)
    return pos
