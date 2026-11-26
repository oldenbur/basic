"""Album order from scanner file names: scanNNNN.k.jpg is print k of album page NNNN."""

import re

_NAME = re.compile(r"scan(\d*)\.*(\d*)", re.I)


def order_key(name: str) -> tuple[int, int, str]:
    """(page, print, name). Names with no page number (scan.jpg) sort last; a missing print number sorts first."""
    m = _NAME.match(name)
    page = int(m[1]) if m and m[1] else 1_000_000
    k = int(m[2]) if m and m[2] else 0
    return page, k, name.lower()


def page_of(name: str) -> int | None:
    page = order_key(name)[0]
    return None if page == 1_000_000 else page
