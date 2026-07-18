"""Offline unit tests for benchmark.py's deterministic reformatting - no API key needed."""
import pandas as pd
import pytest

from benchmark import clean, extract_json, to_partner_a, to_partner_b


def test_clean_handles_nan_and_real_values():
    assert clean(float("nan")) == ""
    assert clean("bailey") == "bailey"


def test_to_partner_a_formats_us_style_date_and_fields():
    row = pd.Series({
        "given_name": "bailey", "surname": "haack", "street_number": "56",
        "address_1": "heysen street", "suburb": "cronulla", "postcode": "2480",
        "state": "nsw", "date_of_birth": "19171029", "soc_sec_id": "5238749",
    })
    rec = to_partner_a("A-001", row)
    assert rec["person_id"] == "A-001"
    assert rec["date_of_birth"] == "10/29/1917"
    assert rec["street"] == "56 heysen street"


def test_to_partner_b_formats_dotted_date_and_camelcase_fields():
    row = pd.Series({
        "given_name": "bailey", "surname": "haack", "street_number": "56",
        "address_1": "heysen street", "suburb": "cronulla", "postcode": "2480",
        "state": "nsw", "date_of_birth": "19171029", "soc_sec_id": "5238749",
    })
    rec = to_partner_b("B-001", row)
    assert rec["personId"] == "B-001"
    assert rec["dateOfBirth"] == "1917.10.29"
    assert rec["streetAddress"] == "heysen street 56"


def test_extract_json_strips_fences():
    assert extract_json('```json\n{"matches": []}\n```') == {"matches": []}


def test_extract_json_raises_clear_error_on_malformed_json():
    with pytest.raises(RuntimeError, match="wasn't valid JSON"):
        extract_json("not json")
