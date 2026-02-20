import re
import os
import pandas as pd
from typing import Optional
from src.models import WarnType

def derive_warn_type(text: Optional[str]) -> Optional[WarnType]:
    if not text:
        return None
    
    text = text.lower()
    
    if "closure" in text or "closing" in text:
        return WarnType.CLOSURE
    
    if "temporary" in text:
        return WarnType.TEMPORARY_LAYOFF
    
    if "permanent" in text or "no recall" in text or "layoff" in text:
        return WarnType.PERMANENT_LAYOFF
        
    return None

def clean_impacted(val: str) -> Optional[int]:
    if not val:
        return None
    # Remove comma and non-numeric chars except digits
    digits = re.sub(r'[^\d]', '', str(val))
    if digits:
        return int(digits)
    return None

def load_fips_places():
    """Load FIPS place names from data/fips.txt."""
    fips_file = 'data/fips.txt'
    if not os.path.exists(fips_file):
        return {}
    
    places = {}
    with open(fips_file, 'r') as f:
        lines = f.readlines()
        
    current_state_fips = None
    
    # Simple parser for the provided FIPS format
    for line in lines:
        line = line.strip()
        if not line or line.startswith('Federal Information') or line.startswith('digits') or line.startswith('using') or line.startswith('identify') or line.startswith('---') or line.startswith('state-level') or line.startswith('county-level'):
            continue
            
        # Try to parse state level: 01 ALABAMA
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 2:
            current_state_fips = parts[0]
            continue
            
        # Try to parse county/place level: 01001 Autauga County
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 5:
            full_fips = parts[0]
            state_fips = full_fips[:2]
            # Join parts starting from index 1 to get the name
            place_name = " ".join(parts[1:])
            
            if state_fips not in places:
                places[state_fips] = []
            
            clean_name = place_name.lower()
            if clean_name not in places[state_fips]:
                places[state_fips].append(clean_name)
                
            # Also add cleaned version without common suffixes
            suffixes = [' county', ' borough', ' census area', ' parish', ' municipality', ' city', ' town', ' village']
            for suffix in suffixes:
                if clean_name.endswith(suffix):
                    cleaned = clean_name[:-len(suffix)].strip()
                    if cleaned and cleaned not in places[state_fips]:
                        places[state_fips].append(cleaned)
                    break

    return places

# Global cache for places
_FIPS_PLACES = None


def standardize_address(street: Optional[str], city: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Standardize street and city according to USPS Pub 28 standards.
    - Uppercase
    - No punctuation
    - Standard abbreviations
    """
    if not street and not city:
        return None, None

    # common suffix abbreviations (subset of USPS Pub 28 Appendix C)
    suffix_map = {
        "AVENUE": "AVE",
        "BOULEVARD": "BLVD",
        "CIRCLE": "CIR",
        "COURT": "CT",
        "DRIVE": "DR",
        "EXPRESSWAY": "EXPY",
        "FREEWAY": "FWY",
        "HIGHWAY": "HWY",
        "LANE": "LN",
        "PARKWAY": "PKWY",
        "PLACE": "PL",
        "ROAD": "RD",
        "SQUARE": "SQ",
        "STREET": "ST",
        "TERRACE": "TER",
        "TRAIL": "TRL",
        "WAY": "WAY", # consistent
        "SUITE": "STE",
        "BUILDING": "BLDG",
        "APARTMENT": "APT",
        "FLOOR": "FL",
        "ROOM": "RM",
        "DEPARTMENT": "DEPT"
    }
    
    def clean_part(part):
        if not part:
            return None
        # Uppercase
        part = part.upper()
        # Remove punctuation (keep hyphens in zip? this function doesn't handle zip)
        part = re.sub(r"[.,'\";:]", "", part)
        
        # Replace suffixes
        tokens = part.split()
        new_tokens = []
        for token in tokens:
            if token in suffix_map:
                new_tokens.append(suffix_map[token])
            else:
                new_tokens.append(token)
        
        return " ".join(new_tokens)

    return clean_part(street), clean_part(city)

def parse_address(address_str, state_fips=None):
    global _FIPS_PLACES
    if _FIPS_PLACES is None:
        _FIPS_PLACES = load_fips_places()

    if not address_str or pd.isna(address_str):
        return {"street": None, "municipality": None, "zip": None}
    
    addr = str(address_str).strip()
    zip_code = None
    city = None
    street = None
    
    # Extract Zip Code using Regex (5 digits, optional 4 extension)
    # Search from end of string backwards effectively by finding all matches and taking last
    matches = list(re.finditer(r'\b(\d{5}(?:-\d{4})?)\b', addr))
    if matches:
        zip_match = matches[-1]
        zip_code = zip_match.group(1)
        # If the match is at the very end of the string (ignoring whitespace/comma), strip it
        start, end = zip_match.span()
        if end >= len(addr.strip()) - 1: # generous tolerance for trailing chars
             addr = addr[:start].strip().rstrip(',')
        
    # Standardize address for city search
    
    # Common city abbreviations map
    city_abbrs = {
        "prov": "Providence",
        "prov.": "Providence",
        "s.f.": "San Francisco",
        "l.a.": "Los Angeles"
    }

    known_cities = []
    if state_fips and state_fips in _FIPS_PLACES:
        known_cities = _FIPS_PLACES[state_fips]
        # Sort by length descending to match longest first
        known_cities.sort(key=len, reverse=True)
        
    extracted_city = None
    
    # Potential address candidates to check for city at end
    # 1. Original address
    # 2. Address with trailing state abbreviation stripped (e.g. "City, CA")
    candidates = [addr]
    
    # Try to strip trailing state abbreviation (2 letters, optional dots/spaces) that might remain after zip extraction
    # Matches ", CA" or " CA" or " Ca" etc at end
    state_strip_match = re.search(r'[, ]+([a-zA-Z]{2})\.?$', addr)
    if state_strip_match:
        # candidate without state
        no_state = addr[:state_strip_match.start()].strip().rstrip(',')
        if no_state:
            candidates.append(no_state)
            
    # print(f"Debug: addr='{addr}', candidates={candidates}")

    if known_cities:
        for candidate in candidates:
            candidate_lower = candidate.lower()
            
            # Check for exact abbreviation match first
            for abbr, full_name in city_abbrs.items():
                if candidate_lower.endswith(abbr):
                     # Verify it's a suffix with boundary
                    suffix_len = len(abbr)
                    if len(candidate) == suffix_len or candidate[-suffix_len-1] in ' ,.':
                         city = full_name
                         street = candidate[:-suffix_len].strip().rstrip(',').strip()
                         extracted_city = city
                         break
            if extracted_city:
                break

            for known_city in known_cities:
                # Check if address ends with this city (case insensitive)
                if candidate_lower.endswith(known_city):
                     # verify word boundary to avoid partial matches like "Weston" matching "Ton"
                    if len(candidate) > len(known_city) and candidate[-len(known_city)-1].isalnum():
                        continue

                    # Extract original casing from candidate? Or use Title Case known city?
                    # Using Title Case for known_city is safer for normalization
                    city = known_city.title() 
                    extracted_city = known_city
                    
                    # The rest is street
                    street = candidate[:-len(known_city)].strip().rstrip(',').strip()
                    break
            if extracted_city:
                break
        if not city:
            # Fallback logic if FIPS failed or no match found
            # Try to use the candidates to strip state if we found one
            target_addr = candidates[-1] if len(candidates) > 1 else addr
            
            parts = target_addr.split(',')
            
            # Special case: If we successfully stripped a state suffix (e.g. "City, ST")
            # and the remaining part has no comma, treat it as a potential city if it doesn't look like a street address.
            if len(candidates) > 1 and len(parts) == 1:
                 # Check if it looks like a street address (starts with number?)
                 # Simple heuristic: if it starts with digit, it's likely a street address or "123 Main St"
                 if not target_addr[0].isdigit():
                     city = target_addr.strip()
                     # street is implicitly None/empty
            
            if not city and len(parts) >= 2:
                # Assume last part is city if we stripped state? 
                # Or if we didn't strip state, maybe last part is State and 2nd to last is City
                
                # If we stripped state, candidates[-1] is "Street, City"
                if len(candidates) > 1:
                     city = parts[-1].strip()
                     street = ",".join(parts[:-1]).strip()
                else:
                    # Original logic for "Street, City, ST"
                     possible_state = parts[-1].strip()
                     if len(possible_state) == 2 and possible_state.isalpha():
                         if len(parts) >= 3:
                            city = parts[-2].strip()
                            street = ",".join(parts[:-2]).strip()
                         else:
                            city = possible_state # Fallback
                            street = ",".join(parts[:-1]).strip()
                     else:
                        city = possible_state
                        street = ",".join(parts[:-1]).strip()
            
            if not city:
                # Suffix splitting fallback on proper candidate
                 # target_addr already selected correctly above
                 suffixes = [
                    ' Blvd', ' St', ' Ave', ' Rd', ' Ln', ' Dr', ' Way', ' Pl', ' Ct', ' Ter', ' Cir', 
                    ' Hwy', ' Pkwy', ' Sq'
                ]
                 for suffix in suffixes:
                    # try with period
                    s_dot = suffix + '.'
                    idx = target_addr.find(s_dot)
                    if idx != -1:
                        street = target_addr[:idx+len(s_dot)].strip()
                        city = target_addr[idx+len(s_dot):].strip().lstrip(',').strip()
                        break
                    
                    # try without period
                    idx = target_addr.find(suffix)
                    if idx != -1:
                        street = target_addr[:idx+len(suffix)].strip()
                        # ensure match boundary
                        if idx+len(suffix) == len(target_addr) or target_addr[idx+len(suffix)] in ' ,':
                            city = target_addr[idx+len(suffix):].strip().lstrip(',').strip()
                            break
                            

    final_street = street if street else None
    
    # Refine street extraction if it contains potential noise (like business name)
    # E.g. "Teamsters Local 251, 1201 Elmwood Ave." -> "1201 Elmwood Ave."
    if final_street and ',' in final_street:
        parts = final_street.split(',')
        # Check parts from end (closest to city) to start
        for part in reversed(parts):
            p_clean = part.strip()
            # Simple heuristic: starts with digit?
            if p_clean and p_clean[0].isdigit():
                final_street = p_clean
                break
                
    final_city = city.title() if city else None
    
    # Apply standardization
    std_street, std_city = standardize_address(final_street, final_city)
    
    return {
        "street": std_street,
        "municipality": std_city,
        "zip": zip_code
    }
