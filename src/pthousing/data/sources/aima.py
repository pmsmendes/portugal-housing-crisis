"""AIMA (ex-SEF): foreign population with legal residence status, by municipality and nationality.

The series reaches us through INE (indicator 0010247, NUTS 2013 geography, 2014 to 2023, ten named
nationalities plus 'other' and the total). INE stops in 2023 because AIMA delayed its data; later municipal
figures exist only in AIMA's migration report as PDF, so this module does not read them.

The count is of people holding a residence title on 31 December, not of people physically present, and it is
affected by administrative processing (see ``docs/data_quality.md``).
"""

from pathlib import Path

from pthousing.data.sources import ine

SOURCE_ID = "aima"
INDICATOR = "0010247"


def fetch(refresh: bool = False) -> list[Path]:
    """Download the INE indicator into ``data/raw/ine/0010247/`` (cached unless ``refresh``)."""
    return ine.fetch_indicator(INDICATOR, refresh=refresh)
