import zipfile

import pytest

from pthousing.data.sources import bp_lending_standards as bp

SHEET = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
<row r="14"><c r="C14" t="s"><v>0</v></c><c r="D14" t="s"><v>1</v></c></row>
<row r="16"><c r="B16" t="s"><v>2</v></c><c r="C16" t="s"><v>2</v></c><c r="D16"><v>55.5</v></c><c r="E16"><v>24</v></c></row>
<row r="17"><c r="C17" t="s"><v>3</v></c><c r="D17"><v>48</v></c></row>
</sheetData></worksheet>"""


@pytest.fixture
def workbook(tmp_path):
    path = tmp_path / "w.xlsx"
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>'
    )
    book = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="G3.1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    strings = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<si><t>Unit</t></si><si><t>Per cent</t></si><si><t>2018 Q3</t></si><si><t>2019</t></si></sst>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", book)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/sharedStrings.xml", strings)
        z.writestr("xl/worksheets/sheet1.xml", SHEET)
    return path


def test_parse_period_handles_years_quarters_and_months():
    assert bp.parse_period("2019") == "2019"
    assert bp.parse_period("2018 Q3") == "2018-Q3"
    assert bp.parse_period("Dec. 25") == "2025-12"
    assert bp.parse_period("Unit") is None
    assert bp.parse_period("Average 2025") == "2025"
    assert bp.parse_period("Average") is None


def test_read_sheet_and_tidy_keep_labelled_rows_and_present_values(workbook):
    rows = bp.read_sheet(workbook, "G3.1")
    assert rows[16][4] == "55.5" and rows[14][3] == "Unit"
    out = bp.tidy(rows, {4: ("a", "pct"), 5: ("b", "pct")}, "G3.1")
    assert sorted(zip(out["indicator"], out["period"], out["value"], strict=True)) == [
        ("a", "2018-Q3", 55.5),
        ("a", "2019", 48.0),
        ("b", "2018-Q3", 24.0),
    ]
