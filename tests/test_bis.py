import pandas as pd
import pytest

from pthousing.data.sources import bis, oecd

CSV_BIS = """FREQ,REF_AREA,VALUE,UNIT_MEASURE,UNIT_MULT,BREAKS,COVERAGE,TITLE_TS,TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK
Q,PT,R,628,0,,,,1988-Q2,100.5,A,F,
Q,PT,N,628,0,,,,1988-Q2,37.0,A,F,
Q,PT,N,628,0,,,,1988-Q1,35.5,A,F,
Q,PT,N,771,0,,,,1989-Q1,4.2,A,F,
"""

CSV_OECD = """STRUCTURE,STRUCTURE_ID,STRUCTURE_NAME,ACTION,REF_AREA,Reference area,FREQ,Frequency of observation,MEASURE,Measure,UNIT_MEASURE,Unit of measure,TIME_PERIOD,Time period,OBS_VALUE,Observation value,OBS_STATUS,Observation status,UNIT_MULT,Unit multiplier,ADJUSTMENT,Adjustment,DECIMALS,Decimals,BASE_PER,Base period
DATAFLOW,X,Y,I,PRT,Portugal,A,Annual,HPI,Nominal,IX,Index,1989,,41.5,,A,N,0,Units,S,SA,1,One,2015,
DATAFLOW,X,Y,I,PRT,Portugal,A,Annual,HPI,Nominal,IX,Index,1988,,40.5,,A,N,0,Units,S,SA,1,One,2015,
DATAFLOW,X,Y,I,PRT,Portugal,A,Annual,HPI_YDH_AVG,Std,PT_AVG_L_TERM,Pct,1995,,113.0,,A,N,0,Units,S,SA,1,One,
"""


@pytest.mark.parametrize(
    ("code", "expected"), [("1988-Q1", "1988-01-01"), ("2026-Q4", "2026-10-01")]
)
def test_bis_parse_period(code, expected):
    assert bis.parse_period(code) == pd.Timestamp(expected)


def test_bis_parse_period_rejects_other_codes():
    with pytest.raises(ValueError):
        bis.parse_period("1988-01")


def test_bis_parse_csv_is_tidy_and_sorted_with_codes_kept_as_text():
    df = bis.parse_csv(CSV_BIS)
    assert list(df["unit"].unique()) == ["628", "771"]
    n = df[(df["basis"] == "N") & (df["unit"] == "628")]
    assert n["period_start"].tolist() == [pd.Timestamp("1988-01-01"), pd.Timestamp("1988-04-01")]
    assert n["value"].tolist() == [35.5, 37.0]
    assert df["quarter"].tolist()[:2] == [2, 1] or set(df["quarter"]) == {1, 2}


def test_oecd_parse_csv_keeps_measure_year_value_and_base():
    df = oecd.parse_csv(CSV_OECD)
    hpi = df[df["measure"] == "HPI"]
    assert hpi["year"].tolist() == [1988, 1989]
    assert hpi["value"].tolist() == [40.5, 41.5]
    assert (hpi["base_year"] == 2015).all()
    assert df[df["measure"] == "HPI_YDH_AVG"]["base_year"].isna().all()
