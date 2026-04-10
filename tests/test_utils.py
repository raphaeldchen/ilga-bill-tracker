import pytest
from services.openstates import normalize_bill_id, to_openstates_identifier, extract_chamber


# ── normalize_bill_id ─────────────────────────────────────────────────────────

def test_normalize_lowercase():
    assert normalize_bill_id("hb1288") == "HB1288"

def test_normalize_with_space():
    assert normalize_bill_id("HB 1288") == "HB1288"

def test_normalize_lowercase_with_space():
    assert normalize_bill_id("hb 1288") == "HB1288"

def test_normalize_mixed_case():
    assert normalize_bill_id("sB0086") == "SB0086"

def test_normalize_leading_trailing_whitespace():
    assert normalize_bill_id("  HB1288  ") == "HB1288"

def test_normalize_already_normalized():
    assert normalize_bill_id("HB1288") == "HB1288"


# ── to_openstates_identifier ──────────────────────────────────────────────────

def test_to_openstates_hb():
    assert to_openstates_identifier("HB1288") == "HB 1288"

def test_to_openstates_sb():
    assert to_openstates_identifier("SB0086") == "SB 0086"

def test_to_openstates_no_match_passes_through():
    # Non-standard IDs are returned unchanged
    assert to_openstates_identifier("UNKNOWN") == "UNKNOWN"


# ── extract_chamber ───────────────────────────────────────────────────────────

def test_extract_chamber_lower():
    action = {"organization": {"classification": "lower", "name": "House"}}
    assert extract_chamber(action) == "House"

def test_extract_chamber_upper():
    action = {"organization": {"classification": "upper", "name": "Senate"}}
    assert extract_chamber(action) == "Senate"

def test_extract_chamber_fallback_by_name_house():
    action = {"organization": {"classification": "", "name": "Illinois House"}}
    assert extract_chamber(action) == "House"

def test_extract_chamber_fallback_by_name_senate():
    action = {"organization": {"classification": "", "name": "Illinois Senate"}}
    assert extract_chamber(action) == "Senate"

def test_extract_chamber_unknown():
    action = {"organization": {"classification": "joint", "name": "Joint Committee"}}
    assert extract_chamber(action) == "joint"

def test_extract_chamber_missing_org():
    assert extract_chamber({}) == "Unknown"
