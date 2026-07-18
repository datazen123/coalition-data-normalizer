"""Offline unit tests for normalize.py's deterministic functions - no API key needed."""
import pytest

from normalize import canon_a, canon_b, extract_json


def test_canon_a_parses_us_date_format():
    rec = {
        "vehicle_id": "A-CT-01", "asset_type": "cargo_truck", "serial_number": "TAC-1",
        "last_service_date": "06/12/2026", "usage_hours": 1420, "fuel_capacity_gal": 60,
        "status": "OPERATIONAL", "location_note": "Lot 3", "notes": "",
    }
    canon = canon_a(rec)
    assert canon["service_date_iso"] == "2026-06-12"
    assert canon["source"] == "A"
    assert canon["source_id"] == "A-CT-01"


def test_canon_b_parses_dotted_date_format_and_converts_liters_to_gallons():
    rec = {
        "vehicleId": "B-0091", "assetType": "cargoTruck", "serialNo": "TAC-1",
        "lastServiceDate": "2026.06.13", "usageHours": 1428, "fuelCapacityL": 227,
        "status": "READY", "locationNote": "Area 3", "notes": "",
    }
    canon = canon_b(rec)
    assert canon["service_date_iso"] == "2026-06-13"
    assert canon["source"] == "B"
    # 227 L / 3.78541 ~= 59.97 gal
    assert canon["fuel_capacity_gal"] == pytest.approx(59.97, abs=0.05)


def test_extract_json_strips_fences():
    assert extract_json('```json\n{"matches": []}\n```') == {"matches": []}


def test_extract_json_raises_clear_error_on_malformed_json():
    with pytest.raises(RuntimeError, match="wasn't valid JSON"):
        extract_json("not json")
