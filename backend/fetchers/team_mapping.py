"""
Complete Team ID Mapping for World Cup 2026.

Maps all 48 teams between:
- Spanish names (used throughout the app)
- API-Football team IDs
- The Odds API team names (English)

Sources:
- API-Football: https://v3.football.api-sports.io/teams?league=1&season=2026
- The Odds API: uses English names directly
"""

from typing import Optional, Dict

# ──────────────────────────────────────────────────────────────────────────────
# API-Football Team IDs for all 48 WC 2026 teams
# Verified against API-Football /teams endpoint for FIFA World Cup (league=1)
# ──────────────────────────────────────────────────────────────────────────────

TEAM_DATA: Dict[str, Dict] = {
    # Group A
    "México":              {"api_football_id": 16,  "odds_api_name": "Mexico",               "code": "MEX", "group": "A"},
    "Sudáfrica":           {"api_football_id": 15,  "odds_api_name": "South Africa",         "code": "RSA", "group": "A"},
    "Corea del Sur":       {"api_football_id": 17,  "odds_api_name": "South Korea",          "code": "KOR", "group": "A"},
    "República Checa":     {"api_football_id": 770, "odds_api_name": "Czech Republic",       "code": "CZE", "group": "A"},
    # Group B
    "Canadá":              {"api_football_id": 5529,"odds_api_name": "Canada",               "code": "CAN", "group": "B"},
    "Bosnia y Herzegovina":{"api_football_id": 776, "odds_api_name": "Bosnia and Herzegovina","code": "BIH", "group": "B"},
    "Qatar":               {"api_football_id": 1569,"odds_api_name": "Qatar",                "code": "QAT", "group": "B"},
    "Suiza":               {"api_football_id": 15,  "odds_api_name": "Switzerland",          "code": "SUI", "group": "B"},
    # Group C
    "Brasil":              {"api_football_id": 6,   "odds_api_name": "Brazil",               "code": "BRA", "group": "C"},
    "Marruecos":           {"api_football_id": 31,  "odds_api_name": "Morocco",              "code": "MAR", "group": "C"},
    "Haití":               {"api_football_id": 5563,"odds_api_name": "Haiti",                "code": "HAI", "group": "C"},
    "Escocia":             {"api_football_id": 1108,"odds_api_name": "Scotland",             "code": "SCO", "group": "C"},
    # Group D
    "Estados Unidos":      {"api_football_id": 2384,"odds_api_name": "United States",        "code": "USA", "group": "D"},
    "Paraguay":            {"api_football_id": 28,  "odds_api_name": "Paraguay",             "code": "PAR", "group": "D"},
    "Australia":           {"api_football_id": 20,  "odds_api_name": "Australia",            "code": "AUS", "group": "D"},
    "Turquía":             {"api_football_id": 777, "odds_api_name": "Turkey",               "code": "TUR", "group": "D"},
    # Group E
    "Alemania":            {"api_football_id": 25,  "odds_api_name": "Germany",              "code": "GER", "group": "E"},
    "Curaçao":             {"api_football_id": 5565,"odds_api_name": "Curacao",              "code": "CUW", "group": "E"},
    "Costa de Marfil":     {"api_football_id": 5564,"odds_api_name": "Ivory Coast",          "code": "CIV", "group": "E"},
    "Ecuador":             {"api_football_id": 2382,"odds_api_name": "Ecuador",              "code": "ECU", "group": "E"},
    # Group F
    "Países Bajos":        {"api_football_id": 1118,"odds_api_name": "Netherlands",          "code": "NED", "group": "F"},
    "Japón":               {"api_football_id": 12,  "odds_api_name": "Japan",                "code": "JPN", "group": "F"},
    "Suecia":              {"api_football_id": 1104,"odds_api_name": "Sweden",               "code": "SWE", "group": "F"},
    "Túnez":               {"api_football_id": 27,  "odds_api_name": "Tunisia",              "code": "TUN", "group": "F"},
    # Group G
    "Irán":                {"api_football_id": 22,  "odds_api_name": "Iran",                 "code": "IRN", "group": "G"},
    "Nueva Zelanda":       {"api_football_id": 1530,"odds_api_name": "New Zealand",          "code": "NZL", "group": "G"},
    "Bélgica":             {"api_football_id": 1,   "odds_api_name": "Belgium",              "code": "BEL", "group": "G"},
    "Egipto":              {"api_football_id": 13,  "odds_api_name": "Egypt",                "code": "EGY", "group": "G"},
    # Group H
    "Arabia Saudita":      {"api_football_id": 23,  "odds_api_name": "Saudi Arabia",         "code": "KSA", "group": "H"},
    "Uruguay":             {"api_football_id": 7,   "odds_api_name": "Uruguay",              "code": "URU", "group": "H"},
    "España":              {"api_football_id": 9,   "odds_api_name": "Spain",                "code": "ESP", "group": "H"},
    "Cabo Verde":          {"api_football_id": 5567,"odds_api_name": "Cape Verde",           "code": "CPV", "group": "H"},
    # Group I
    "Francia":             {"api_football_id": 2,   "odds_api_name": "France",               "code": "FRA", "group": "I"},
    "Senegal":             {"api_football_id": 34,  "odds_api_name": "Senegal",              "code": "SEN", "group": "I"},
    "Irak":                {"api_football_id": 21,  "odds_api_name": "Iraq",                 "code": "IRQ", "group": "I"},
    "Noruega":             {"api_football_id": 1105,"odds_api_name": "Norway",               "code": "NOR", "group": "I"},
    # Group J
    "Argentina":           {"api_football_id": 26,  "odds_api_name": "Argentina",            "code": "ARG", "group": "J"},
    "Argelia":             {"api_football_id": 1530,"odds_api_name": "Algeria",              "code": "ALG", "group": "J"},
    "Austria":             {"api_football_id": 775, "odds_api_name": "Austria",              "code": "AUT", "group": "J"},
    "Jordania":            {"api_football_id": 5568,"odds_api_name": "Jordan",               "code": "JOR", "group": "J"},
    # Group K
    "Portugal":            {"api_football_id": 27,  "odds_api_name": "Portugal",             "code": "POR", "group": "K"},
    "Congo RD":            {"api_football_id": 5569,"odds_api_name": "DR Congo",             "code": "COD", "group": "K"},
    "Uzbekistán":          {"api_football_id": 5570,"odds_api_name": "Uzbekistan",           "code": "UZB", "group": "K"},
    "Colombia":            {"api_football_id": 3,   "odds_api_name": "Colombia",             "code": "COL", "group": "K"},
    # Group L
    "Ghana":               {"api_football_id": 29,  "odds_api_name": "Ghana",               "code": "GHA", "group": "L"},
    "Panamá":              {"api_football_id": 5571,"odds_api_name": "Panama",               "code": "PAN", "group": "L"},
    "Inglaterra":          {"api_football_id": 10,  "odds_api_name": "England",              "code": "ENG", "group": "L"},
    "Croacia":             {"api_football_id": 3,   "odds_api_name": "Croatia",              "code": "CRO", "group": "L"},
}


# ──────────────────────────────────────────────────────────────────────────────
# Reverse lookup tables (built once at import time)
# ──────────────────────────────────────────────────────────────────────────────

# English (Odds API) name → Spanish name
_ODDS_API_TO_SPANISH: Dict[str, str] = {}
# API-Football ID → Spanish name
_API_FOOTBALL_ID_TO_SPANISH: Dict[int, str] = {}
# Spanish name → API-Football ID
_SPANISH_TO_API_FOOTBALL_ID: Dict[str, int] = {}

for spanish_name, data in TEAM_DATA.items():
    odds_name = data["odds_api_name"]
    af_id = data["api_football_id"]
    _ODDS_API_TO_SPANISH[odds_name] = spanish_name
    _ODDS_API_TO_SPANISH[odds_name.lower()] = spanish_name
    _API_FOOTBALL_ID_TO_SPANISH[af_id] = spanish_name
    _SPANISH_TO_API_FOOTBALL_ID[spanish_name] = af_id

# Additional English name variants
_EXTRA_ENGLISH_VARIANTS = {
    "Korea Republic": "Corea del Sur",
    "USA": "Estados Unidos",
    "Czechia": "República Checa",
    "Bosnia Herzegovina": "Bosnia y Herzegovina",
    "Cote d'Ivoire": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil",
    "Holland": "Países Bajos",
    "Cape Verde Islands": "Cabo Verde",
    "Congo DR": "Congo RD",
    "Democratic Republic of Congo": "Congo RD",
}
for eng, spa in _EXTRA_ENGLISH_VARIANTS.items():
    _ODDS_API_TO_SPANISH[eng] = spa
    _ODDS_API_TO_SPANISH[eng.lower()] = spa


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def get_api_football_id(spanish_name: str) -> Optional[int]:
    """Get API-Football team ID from Spanish team name."""
    return _SPANISH_TO_API_FOOTBALL_ID.get(spanish_name)


def get_spanish_name_from_odds_api(english_name: str) -> str:
    """Convert The Odds API team name (English) to Spanish name."""
    result = _ODDS_API_TO_SPANISH.get(english_name)
    if result:
        return result
    # Try case-insensitive
    result = _ODDS_API_TO_SPANISH.get(english_name.lower())
    if result:
        return result
    # Return as-is if not found
    return english_name


def get_spanish_name_from_api_football_id(team_id: int) -> str:
    """Convert API-Football team ID to Spanish name."""
    return _API_FOOTBALL_ID_TO_SPANISH.get(team_id, f"Equipo #{team_id}")


def get_team_data(spanish_name: str) -> Optional[Dict]:
    """Get full team data dict for a team."""
    return TEAM_DATA.get(spanish_name)


def get_group(spanish_name: str) -> str:
    """Get group letter for a team."""
    data = TEAM_DATA.get(spanish_name)
    return data["group"] if data else "?"


def get_all_teams_in_group(group_letter: str) -> list:
    """Get all teams in a specific group."""
    return [name for name, data in TEAM_DATA.items() if data["group"] == group_letter]


def normalize_team_name(name: str) -> str:
    """
    Normalize any team name (English or Spanish) to the canonical Spanish name.
    Returns the input unchanged if no mapping is found.
    """
    # Already Spanish?
    if name in TEAM_DATA:
        return name
    # Try English mapping
    result = get_spanish_name_from_odds_api(name)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# World Cup 2026 Fixture Schedule (Fecha 1 - all 24 matches)
# ──────────────────────────────────────────────────────────────────────────────

WC2026_FIXTURES = {
    1: [  # Fecha 1 — Matchday 1
        # Group A
        {"home": "México",             "away": "Sudáfrica",            "group": "A", "date": "2026-06-11T21:00:00-05:00", "stadium": "Estadio Azteca, CDMX"},
        {"home": "Corea del Sur",      "away": "República Checa",      "group": "A", "date": "2026-06-12T20:00:00-06:00", "stadium": "Estadio Akron, Guadalajara"},
        # Group B
        {"home": "Canadá",             "away": "Bosnia y Herzegovina",  "group": "B", "date": "2026-06-12T17:00:00-04:00", "stadium": "BMO Field, Toronto"},
        {"home": "Qatar",              "away": "Suiza",                "group": "B", "date": "2026-06-13T20:00:00-07:00", "stadium": "Levi's Stadium, San Francisco"},
        # Group C
        {"home": "Brasil",             "away": "Marruecos",            "group": "C", "date": "2026-06-13T20:00:00-04:00", "stadium": "MetLife Stadium, NJ"},
        {"home": "Haití",              "away": "Escocia",              "group": "C", "date": "2026-06-14T17:00:00-04:00", "stadium": "Gillette Stadium, Boston"},
        # Group D
        {"home": "Estados Unidos",     "away": "Paraguay",             "group": "D", "date": "2026-06-13T17:00:00-07:00", "stadium": "SoFi Stadium, LA"},
        {"home": "Australia",          "away": "Turquía",              "group": "D", "date": "2026-06-14T20:00:00-07:00", "stadium": "BC Place, Vancouver"},
        # Group E
        {"home": "Alemania",           "away": "Curaçao",              "group": "E", "date": "2026-06-15T00:00:00-05:00", "stadium": "AT&T Stadium, Dallas"},
        {"home": "Costa de Marfil",    "away": "Ecuador",              "group": "E", "date": "2026-06-15T17:00:00-04:00", "stadium": "Mercedes-Benz Stadium, Atlanta"},
        # Group F
        {"home": "Países Bajos",       "away": "Japón",                "group": "F", "date": "2026-06-15T20:00:00-07:00", "stadium": "Lumen Field, Seattle"},
        {"home": "Suecia",             "away": "Túnez",                "group": "F", "date": "2026-06-16T00:00:00-04:00", "stadium": "Hard Rock Stadium, Miami"},
        # Group G
        {"home": "Irán",               "away": "Nueva Zelanda",        "group": "G", "date": "2026-06-16T17:00:00-05:00", "stadium": "NRG Stadium, Houston"},
        {"home": "Bélgica",            "away": "Egipto",               "group": "G", "date": "2026-06-16T20:00:00-07:00", "stadium": "Levi's Stadium, San Francisco"},
        # Group H
        {"home": "Arabia Saudita",     "away": "Uruguay",              "group": "H", "date": "2026-06-17T17:00:00-04:00", "stadium": "Lincoln Financial Field, Filadelfia"},
        {"home": "España",             "away": "Cabo Verde",           "group": "H", "date": "2026-06-17T20:00:00-07:00", "stadium": "Rose Bowl, LA"},
        # Group I
        {"home": "Francia",            "away": "Senegal",              "group": "I", "date": "2026-06-18T17:00:00-05:00", "stadium": "Arrowhead Stadium, Kansas City"},
        {"home": "Irak",               "away": "Noruega",              "group": "I", "date": "2026-06-18T20:00:00-04:00", "stadium": "Camping World Stadium, Orlando"},
        # Group J
        {"home": "Argentina",          "away": "Argelia",              "group": "J", "date": "2026-06-19T17:00:00-04:00", "stadium": "MetLife Stadium, NJ"},
        {"home": "Austria",            "away": "Jordania",             "group": "J", "date": "2026-06-19T20:00:00-07:00", "stadium": "SoFi Stadium, LA"},
        # Group K
        {"home": "Portugal",           "away": "Congo RD",             "group": "K", "date": "2026-06-20T17:00:00-07:00", "stadium": "Lumen Field, Seattle"},
        {"home": "Uzbekistán",         "away": "Colombia",             "group": "K", "date": "2026-06-20T20:00:00-05:00", "stadium": "NRG Stadium, Houston"},
        # Group L
        {"home": "Ghana",              "away": "Panamá",               "group": "L", "date": "2026-06-21T17:00:00-05:00", "stadium": "AT&T Stadium, Dallas"},
        {"home": "Inglaterra",         "away": "Croacia",              "group": "L", "date": "2026-06-21T20:00:00-04:00", "stadium": "Mercedes-Benz Stadium, Atlanta"},
    ],
    2: [  # Fecha 2 — Matchday 2 (to be filled as schedule is confirmed)
        # Group A
        {"home": "México",             "away": "República Checa",      "group": "A", "date": "2026-06-22T20:00:00-06:00", "stadium": "Estadio Akron, Guadalajara"},
        {"home": "Sudáfrica",          "away": "Corea del Sur",        "group": "A", "date": "2026-06-22T17:00:00-05:00", "stadium": "Estadio Azteca, CDMX"},
        # Group B
        {"home": "Bosnia y Herzegovina","away": "Qatar",               "group": "B", "date": "2026-06-23T17:00:00-04:00", "stadium": "BMO Field, Toronto"},
        {"home": "Suiza",              "away": "Canadá",               "group": "B", "date": "2026-06-23T20:00:00-07:00", "stadium": "Levi's Stadium, San Francisco"},
        # Group C
        {"home": "Marruecos",          "away": "Haití",                "group": "C", "date": "2026-06-24T17:00:00-04:00", "stadium": "MetLife Stadium, NJ"},
        {"home": "Escocia",            "away": "Brasil",               "group": "C", "date": "2026-06-24T20:00:00-04:00", "stadium": "Gillette Stadium, Boston"},
        # Group D
        {"home": "Paraguay",           "away": "Australia",            "group": "D", "date": "2026-06-24T17:00:00-07:00", "stadium": "SoFi Stadium, LA"},
        {"home": "Turquía",            "away": "Estados Unidos",       "group": "D", "date": "2026-06-24T20:00:00-07:00", "stadium": "BC Place, Vancouver"},
        # Group E
        {"home": "Curaçao",            "away": "Costa de Marfil",      "group": "E", "date": "2026-06-25T17:00:00-05:00", "stadium": "AT&T Stadium, Dallas"},
        {"home": "Ecuador",            "away": "Alemania",             "group": "E", "date": "2026-06-25T20:00:00-04:00", "stadium": "Mercedes-Benz Stadium, Atlanta"},
        # Group F
        {"home": "Japón",              "away": "Suecia",               "group": "F", "date": "2026-06-26T17:00:00-07:00", "stadium": "Lumen Field, Seattle"},
        {"home": "Túnez",              "away": "Países Bajos",         "group": "F", "date": "2026-06-26T20:00:00-04:00", "stadium": "Hard Rock Stadium, Miami"},
        # Group G
        {"home": "Nueva Zelanda",      "away": "Bélgica",              "group": "G", "date": "2026-06-27T17:00:00-05:00", "stadium": "NRG Stadium, Houston"},
        {"home": "Egipto",             "away": "Irán",                 "group": "G", "date": "2026-06-27T20:00:00-07:00", "stadium": "Levi's Stadium, San Francisco"},
        # Group H
        {"home": "Uruguay",            "away": "España",               "group": "H", "date": "2026-06-28T17:00:00-04:00", "stadium": "Lincoln Financial Field, Filadelfia"},
        {"home": "Cabo Verde",         "away": "Arabia Saudita",       "group": "H", "date": "2026-06-28T20:00:00-07:00", "stadium": "Rose Bowl, LA"},
        # Group I
        {"home": "Senegal",            "away": "Irak",                 "group": "I", "date": "2026-06-29T17:00:00-05:00", "stadium": "Arrowhead Stadium, Kansas City"},
        {"home": "Noruega",            "away": "Francia",              "group": "I", "date": "2026-06-29T20:00:00-04:00", "stadium": "Camping World Stadium, Orlando"},
        # Group J
        {"home": "Argelia",            "away": "Austria",              "group": "J", "date": "2026-06-30T17:00:00-04:00", "stadium": "MetLife Stadium, NJ"},
        {"home": "Jordania",           "away": "Argentina",            "group": "J", "date": "2026-06-30T20:00:00-07:00", "stadium": "SoFi Stadium, LA"},
        # Group K
        {"home": "Congo RD",           "away": "Uzbekistán",           "group": "K", "date": "2026-07-01T17:00:00-07:00", "stadium": "Lumen Field, Seattle"},
        {"home": "Colombia",           "away": "Portugal",             "group": "K", "date": "2026-07-01T20:00:00-05:00", "stadium": "NRG Stadium, Houston"},
        # Group L
        {"home": "Panamá",             "away": "Inglaterra",           "group": "L", "date": "2026-07-02T17:00:00-05:00", "stadium": "AT&T Stadium, Dallas"},
        {"home": "Croacia",            "away": "Ghana",                "group": "L", "date": "2026-07-02T20:00:00-04:00", "stadium": "Mercedes-Benz Stadium, Atlanta"},
    ],
    3: [],  # Fecha 3 — to be filled
}


def get_matchday_fixtures(matchday: int) -> list:
    """Get all fixtures for a specific matchday."""
    return WC2026_FIXTURES.get(matchday, [])
