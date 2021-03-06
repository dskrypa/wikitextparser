"""Define the ParserFunction class."""
from bisect import insort, bisect_right
from typing import List

import regex

from ._wikitext import SubWikiText
from ._argument import Argument
from ._wikilist import WikiList


PF_NAME_ARGS_FULLMATCH = regex.compile(
    rb'[^:|}]*+'  # name
    rb'(?<arg>:[^|]*+)?+(?<arg>\|[^|]*+)*+'
).fullmatch


class SubWikiTextWithArgs(SubWikiText):

    """Define common attributes for `Template` and `ParserFunction`."""

    _name_args_matcher = NotImplemented
    _first_arg_sep = 0

    @property
    def nesting_level(self) -> int:
        """Return the nesting level of self.

        The minimum nesting_level is 0. Being part of any Template or
        ParserFunction increases the level by one.
        """
        return self._nesting_level(('Template', 'ParserFunction'))

    @property
    def arguments(self) -> List[Argument]:
        """Parse template content. Create self.name and self.arguments."""
        shadow = self._shadow
        split_spans = self._name_args_matcher(shadow, 2, -2).spans('arg')
        if not split_spans:
            return []
        arguments = []
        arguments_append = arguments.append
        type_to_spans = self._type_to_spans
        ss, se = span = self._span
        type_ = id(span)
        lststr = self._lststr
        string = lststr[0]
        arg_spans = type_to_spans.setdefault(type_, [])
        span_tuple_to_span_get = {(s[0], s[1]): s for s in arg_spans}.get
        for arg_self_start, arg_self_end in split_spans:
            s, e = arg_span = [ss + arg_self_start, ss + arg_self_end]
            old_span = span_tuple_to_span_get((s, e))
            if old_span is None:
                insort(arg_spans, arg_span)
            else:
                arg_span = old_span
            arg = Argument(lststr, type_to_spans, arg_span, type_)
            arg._shadow_cache = (
                string[s:e], shadow[arg_self_start:arg_self_end])
            arguments_append(arg)
        return arguments

    def lists(self, pattern: str = None) -> List[WikiList]:
        """Return the lists in all arguments.

        For performance reasons it is usually preferred to get a specific
        Argument and use the `lists` method of that argument instead.
        """
        return [
            lst for arg in self.arguments for lst in arg.lists(pattern) if lst]

    @property
    def name(self) -> str:
        """Template's name (includes whitespace).

        getter: Return the name.
        setter: Set a new name.
        """
        sep = self._shadow.find(self._first_arg_sep)
        if sep == -1:
            return self(2, -2)
        return self(2, sep)

    @name.setter
    def name(self, newname: str) -> None:
        self[2:2 + len(self.name)] = newname


class ParserFunction(SubWikiTextWithArgs):

    """Create a new ParserFunction object."""

    _name_args_matcher = PF_NAME_ARGS_FULLMATCH
    _first_arg_sep = 58
