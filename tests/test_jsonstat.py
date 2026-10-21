import pandas as pd

from pthousing.data.sources.jsonstat import parse_jsonstat


def _dims(**cats):
    return {k: {"category": {"index": v}} for k, v in cats.items()}


def test_dense_values_with_status_list():
    payload = {
        "id": ["geo", "time"],
        "size": [2, 3],
        "dimension": _dims(geo=["PT", "ES"], time=["2020", "2021", "2022"]),
        "value": [1.0, 2.0, 3.0, 4.0, None, 6.0],
        "status": ["F", "F", "P", "F", "F", "F"],
    }
    df = parse_jsonstat(payload)
    assert len(df) == 5  # the None cell is omitted
    assert df.loc[(df.geo == "ES") & (df.time == "2020"), "value"].item() == 4.0
    assert df.loc[(df.geo == "PT") & (df.time == "2022"), "status"].item() == "P"
    assert not ((df.geo == "ES") & (df.time == "2021")).any()


def test_sparse_values_and_index_given_as_code_to_position_dict():
    payload = {
        "id": ["geo", "time"],
        "size": [2, 3],
        "dimension": _dims(geo={"ES": 1, "PT": 0}, time={"2020": 0, "2021": 1, "2022": 2}),
        "value": {"1": 11.0, "5": 55.0},
        "status": {"5": "p"},
    }
    df = parse_jsonstat(payload).set_index(["geo", "time"])
    assert df.loc[("PT", "2021"), "value"] == 11.0
    assert df.loc[("ES", "2022"), "value"] == 55.0
    assert df.loc[("ES", "2022"), "status"] == "p"
    assert pd.isna(df.loc[("PT", "2021"), "status"])
    assert len(df) == 2


def test_empty_dataset_gives_empty_frame_with_columns():
    payload = {"id": ["geo"], "size": [1], "dimension": _dims(geo=["PT"]), "value": {}}
    df = parse_jsonstat(payload)
    assert df.empty and {"geo", "value", "status"} <= set(df.columns)
