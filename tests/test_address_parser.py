import pytest
from src.utils import parse_address

@pytest.mark.parametrize("address_input, state_fips, expected_municipality, expected_street", [
    ("13963 Alondra Blvd. Santa Fe Springs Ca", "06", "SANTA FE SPRINGS", "13963 ALONDRA BLVD"), # wait, "Santa Fe Springs" -> "SAN FE SPRINGS"? "TA" removed? No. "SANTA" is not in abbreviation map I added yet.
    # Ah, "Santa" -> "SANTA" (uppercase). "Fe" -> "FE". "Springs" -> "SPRINGS".
    # Punctuation removed.
    
    ("13963 Alondra Blvd. Santa Fe Springs Ca", "06", "SANTA FE SPRINGS", "13963 ALONDRA BLVD"),
    ("5651 Copley Dr. Suite A  San Diego Ca", "06", "SAN DIEGO", "5651 COPLEY DR STE A"),
    ("2425 Saybrook Ave 90040", "06", None, "2425 SAYBROOK AVE"),
    ("East Greenwich, RI", "44", "EAST GREENWICH", None),
    ("Lincoln, RI", "44", "LINCOLN", None),
    ("Teamsters Local 251, 1201 Elmwood Ave., Prov., RI 02907", "44", "PROVIDENCE", "1201 ELMWOOD AVE"),
    ("8695 Spectrum Center Blvd. San Diego Ca", "06", "SAN DIEGO", "8695 SPECTRUM CENTER BLVD")
])
def test_parse_address(address_input, state_fips, expected_municipality, expected_street):
    result = parse_address(address_input, state_fips=state_fips)
    
    # Allow loose matching for street to handle minor punctuation diffs if needed, 
    # but for now expect exact or close enough.
    
    if expected_municipality:
        # Check if result municipality starts with expected (to handle "Providence" matching "Prov.") or vice versa?
        # The parser seems to capitalize.
        assert result['municipality'] == expected_municipality
    else:
        assert result['municipality'] is None

    if expected_street:
        # Normalize street for comparison (strip periods maybe?)
        # Let's try exact match first
        assert result['street'] == expected_street
    else:
        assert result['street'] is None
