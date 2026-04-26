"""
strconv.py - String case conversion utilities for the Ayuna framework.

This module provides comprehensive string case conversion functionality:

- Simple conversions: lower_with_underscores, lower_with_hyphens
- CaseConverter class with methods for:
  - kebab-case
  - camelCase
  - PascalCase
  - snake_case
  - COBOL-CASE
  - MACRO_CASE
  - flatlower
  - FLATUPPER

The conversion system uses a token marker pattern for flexible handling
of different character transitions (delimiter, case changes).
"""

import re
import string
from abc import ABC, abstractmethod
from io import StringIO
from typing import List

from pydantic import BaseModel, ConfigDict

from ..basetypes import AyunaError
from ..constants import ALLCHARS_REGEX, DEFAULT_WORD_DELIMITERS

# =============================================================================
# Simple Conversion Functions
# =============================================================================


def lower_with_underscores(in_str: str):
    """
    Convert a string to lowercase and replace all delimiters with underscores.

    Parameters
    ----------
    in_str : str
        Input string to convert.

    Returns
    -------
    str
        Lowercase string with underscores replacing delimiters.
    """
    return re.sub(
        ALLCHARS_REGEX.format(re.escape(DEFAULT_WORD_DELIMITERS)), "_", in_str
    ).lower()


def lower_with_hyphens(in_str: str):
    """
    Convert a string to lowercase and replace all delimiters with hyphens.

    Parameters
    ----------
    in_str : str
        Input string to convert.

    Returns
    -------
    str
        Lowercase string with hyphens replacing delimiters.
    """
    return re.sub(
        ALLCHARS_REGEX.format(re.escape(DEFAULT_WORD_DELIMITERS)), "-", in_str
    ).lower()


# =============================================================================
# Token Marker System
# =============================================================================


class TokenMarkerArgs(BaseModel):
    """
    Arguments container for TokenMarker instances.

    Holds the shared state and configuration for token markers
    during string case conversion.

    Attributes
    ----------
    in_buffer : StringIO
        Input buffer to read characters from.
    out_buffer : StringIO
        Output buffer to write converted characters to.
    join_char : str
        Character to insert between tokens (e.g., "-" for kebab-case).
    delimiters : str
        Characters that mark word boundaries.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    in_buffer: StringIO
    out_buffer: StringIO
    join_char: str = ""
    delimiters: str = DEFAULT_WORD_DELIMITERS


class TokenMarker(ABC):
    """
    Abstract base class for token boundary markers.

    Token markers detect specific character patterns (like delimiter
    followed by letter, or lowercase followed by uppercase) and emit
    appropriately transformed characters to the output buffer.

    Subclasses implement the `mark()` method to handle specific patterns.
    """

    def __init__(self, tmargs: TokenMarkerArgs):
        """
        Initialize the token marker with shared arguments.

        Parameters
        ----------
        tmargs : TokenMarkerArgs
            Configuration and buffers for the conversion.
        """
        self._delimiters = tmargs.delimiters
        self._join_char = tmargs.join_char
        self._in_buffer = tmargs.in_buffer
        self._out_buffer = tmargs.out_buffer

    @abstractmethod
    def mark(self, curr_char: str, prev_char: str | None) -> bool:
        """
        Process a character and emit transformed output if this marker matches.

        Parameters
        ----------
        curr_char : str
            The current character being processed.
        prev_char : str | None
            The previous character, or None if at start.

        Returns
        -------
        bool
            True if this marker handled the character, False otherwise.
        """
        raise NotImplementedError()


class OnDelimiterNextUpperMarker(TokenMarker):
    """Marker: On delimiter, emit join char and next char as uppercase."""

    def __init__(self, tmargs: TokenMarkerArgs):
        super().__init__(tmargs)

    def mark(self, curr_char: str, prev_char: str | None = None):
        if curr_char not in self._delimiters:
            return False

        self._out_buffer.write(self._join_char)
        self._out_buffer.write(self._in_buffer.read(1).upper())

        return True


class OnDelimiterNextLowerMarker(TokenMarker):
    """Marker: On delimiter, emit join char and next char as lowercase."""

    def __init__(self, tmargs: TokenMarkerArgs):
        super().__init__(tmargs)

    def mark(self, curr_char: str, prev_char: str | None = None):
        if curr_char not in self._delimiters:
            return False

        self._out_buffer.write(self._join_char)
        self._out_buffer.write(self._in_buffer.read(1).lower())

        return True


class OnLowerUpperAppendUpperMarker(TokenMarker):
    """Marker: On lowercase->uppercase transition, emit join char and uppercase."""

    def __init__(self, tmargs: TokenMarkerArgs):
        super().__init__(tmargs)

    def mark(self, curr_char: str, prev_char: str | None = None):
        if (
            prev_char is None
            or not prev_char.isalpha()
            or not prev_char.islower()
            or not curr_char.isupper()
        ):
            return False

        self._out_buffer.write(self._join_char)
        self._out_buffer.write(curr_char)

        return True


class OnLowerUpperAppendLowerMarker(TokenMarker):
    """Marker: On lowercase->uppercase transition, emit join char and lowercase."""

    def __init__(self, tmargs: TokenMarkerArgs):
        super().__init__(tmargs)

    def mark(self, curr_char: str, prev_char: str | None = None):
        if (
            prev_char is None
            or not prev_char.isalpha()
            or not prev_char.islower()
            or not curr_char.isupper()
        ):
            return False

        self._out_buffer.write(self._join_char)
        self._out_buffer.write(curr_char.lower())

        return True


class OnUpperUpperAppendJoinMarker(TokenMarker):
    """Marker: On uppercase->uppercase, emit join char and current char."""

    def __init__(self, tmargs: TokenMarkerArgs):
        super().__init__(tmargs)

    def mark(self, curr_char: str, prev_char: str | None = None):
        if (
            prev_char is None
            or not prev_char.isalpha()
            or not prev_char.isupper()
            or not curr_char.isupper()
        ):
            return False

        self._out_buffer.write(self._join_char)
        self._out_buffer.write(curr_char)

        return True


class OnUpperUpperAppendCurrentMarker(TokenMarker):
    """Marker: On uppercase->uppercase, emit current char only (no join)."""

    def __init__(self, tmargs: TokenMarkerArgs):
        super().__init__(tmargs)

    def mark(self, curr_char: str, prev_char: str | None = None):
        if (
            prev_char is None
            or not prev_char.isalpha()
            or not prev_char.isupper()
            or not curr_char.isupper()
        ):
            return False

        self._out_buffer.write(curr_char)

        return True


# =============================================================================
# Case Converter
# =============================================================================


class CaseConverter:
    """
    Static utility class for converting strings between different case styles.

    Supports conversion from any input format (with configurable delimiters)
    to various standard case styles: kebab-case, camelCase, PascalCase,
    snake_case, COBOL-CASE, MACRO_CASE, flatlower, and FLATUPPER.

    All methods are static and handle mixed-case input, delimiters, and
    punctuation automatically.
    """

    @staticmethod
    def _prepared_string(in_str: str, delimiters: str, clear_punctuation: bool) -> str:
        if not in_str:
            raise AyunaError("Empty string passed for conversion")

        ## Step 1: Strip delimiters
        out_str = in_str.strip(delimiters)

        ## Step 2: Remove non-delimiter punctuation
        if clear_punctuation:
            punc = "".join([ch for ch in string.punctuation if ch not in delimiters])
            out_str = re.sub(ALLCHARS_REGEX.format(re.escape(punc)), "", out_str)

        ## Step 3: Replace recurring delimiters with a single one
        out_str = re.sub(
            ALLCHARS_REGEX.format(re.escape(delimiters)), delimiters[0], out_str
        )

        ## Step 4: Convert the string to lowercase
        out_str = out_str.lower() if out_str.isupper() else out_str

        return out_str

    @staticmethod
    def _process_markers(
        token_markers: List[TokenMarker],
        in_buffer: StringIO,
        out_buffer: StringIO,
        unmarked_upper: bool = False,
    ):
        prev_ch = None
        curr_ch = in_buffer.read(1)

        while curr_ch:
            is_marked = False

            for marker in token_markers:
                if marker.mark(curr_char=curr_ch, prev_char=prev_ch):
                    is_marked = True
                    break

            if not is_marked:
                out_buffer.write(curr_ch.upper() if unmarked_upper else curr_ch.lower())

            prev_ch = curr_ch
            curr_ch = in_buffer.read(1)

    @staticmethod
    def to_kebabcase(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to kebab-case.

        Parameters
        ----------
        in_str: str
            The string to be converted to kebab-case
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The kebab-case string
        """
        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            delimiters=delimiters,
            join_char="-",
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextLowerMarker(tmargs),
            OnLowerUpperAppendLowerMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers, in_buffer=in_buffer, out_buffer=out_buffer
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_camelcase(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to camelCase.

        Parameters
        ----------
        in_str: str
            The string to be converted to camelCase
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The camelCase string
        """
        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer, out_buffer=out_buffer, delimiters=delimiters
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextUpperMarker(tmargs),
            OnLowerUpperAppendUpperMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers, in_buffer=in_buffer, out_buffer=out_buffer
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_pascalcase(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to PascalCase.

        Parameters
        ----------
        in_str: str
            The string to be converted to PascalCase
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The PascalCase string
        """
        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer, out_buffer=out_buffer, delimiters=delimiters
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextUpperMarker(tmargs),
            OnLowerUpperAppendUpperMarker(tmargs),
            OnUpperUpperAppendCurrentMarker(tmargs),
        ]

        out_buffer.write(in_buffer.read(1).upper())
        CaseConverter._process_markers(
            token_markers=token_markers, in_buffer=in_buffer, out_buffer=out_buffer
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_snakecase(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to snake_case.

        Parameters
        ----------
        in_str: str
            The string to be converted to snake_case
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The snake_case string
        """
        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            delimiters=delimiters,
            join_char="_",
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextLowerMarker(tmargs),
            OnLowerUpperAppendLowerMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers, in_buffer=in_buffer, out_buffer=out_buffer
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_cobolcase(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to COBOLCase.

        Parameters
        ----------
        in_str: str
            The string to be converted to COBOLCase
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The COBOLCase string
        """
        join_ch = "-"

        if in_str.isupper():
            return re.sub(ALLCHARS_REGEX.format(re.escape(delimiters)), join_ch, in_str)

        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            delimiters=delimiters,
            join_char=join_ch,
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextUpperMarker(tmargs),
            OnLowerUpperAppendUpperMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers,
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            unmarked_upper=True,
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_macrocase(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to MACRO_CASE.

        Parameters
        ----------
        in_str: str
            The string to be converted to MACRO_CASE
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The MACRO_CASE string
        """
        join_ch = "_"

        if in_str.isupper():
            return re.sub(ALLCHARS_REGEX.format(re.escape(delimiters)), join_ch, in_str)

        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            delimiters=delimiters,
            join_char=join_ch,
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextUpperMarker(tmargs),
            OnLowerUpperAppendUpperMarker(tmargs),
            OnUpperUpperAppendJoinMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers,
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            unmarked_upper=True,
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_flatlower(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to flatlower (i.e., removing all delimiters and converting to lowercase).

        Parameters
        ----------
        in_str: str
            The string to be converted to flatlower
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The flatlower string
        """
        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer, out_buffer=out_buffer, delimiters=delimiters
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextLowerMarker(tmargs),
            OnLowerUpperAppendLowerMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers, in_buffer=in_buffer, out_buffer=out_buffer
        )

        return out_buffer.getvalue()

    @staticmethod
    def to_flatupper(
        in_str: str,
        delimiters: str = DEFAULT_WORD_DELIMITERS,
        clear_punctuation: bool = True,
    ) -> str:
        """
        Convert a string to FLATUPPER (i.e., removing all delimiters and converting to uppercase).

        Parameters
        ----------
        in_str: str
            The string to be converted to FLATUPPER
        delimiters: str
            The delimiters to be used to separate words
        clear_punctuation: bool
            True to remove non-delimiter punctuation, False otherwise

        Returns
        -------
        str
            The FLATUPPER string
        """
        out_str = CaseConverter._prepared_string(
            in_str=in_str, delimiters=delimiters, clear_punctuation=clear_punctuation
        )

        in_buffer = StringIO(out_str)
        out_buffer = StringIO()

        tmargs = TokenMarkerArgs(
            in_buffer=in_buffer, out_buffer=out_buffer, delimiters=delimiters
        )
        token_markers: List[TokenMarker] = [
            OnDelimiterNextUpperMarker(tmargs),
            OnLowerUpperAppendUpperMarker(tmargs),
        ]

        CaseConverter._process_markers(
            token_markers=token_markers,
            in_buffer=in_buffer,
            out_buffer=out_buffer,
            unmarked_upper=True,
        )

        return out_buffer.getvalue()
