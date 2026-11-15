"""Geografia della ricerca: i Paesi Bassi devono essere un paese sceglibile."""
from app.core.config import JOB_BOARDS, get_boards_for_country
from app.services import geo
from app.services.normalize import country_code


def test_paesi_bassi_nel_menu_paese():
    codes = [c["code"] for c in geo.tree()["countries"]]
    assert "NL" in codes


def test_paesi_bassi_nomi():
    # In italiano per l'utente, in inglese per i portali globali (ADR-019)
    assert geo.display_name("NL") == "Paesi Bassi"
    assert geo.search_name("nl") == "Netherlands"


def test_paesi_bassi_province():
    regions = geo.regions_for("NL")
    assert len(regions) == 12
    assert "Noord-Holland" in regions
    assert geo.is_valid_region("NL", "Utrecht")
    # una provincia olandese non vale per un altro paese
    assert not geo.is_valid_region("DE", "Utrecht")


def test_paesi_bassi_hanno_portali():
    # geo.json: un paese senza portali in JOB_BOARDS non serve a niente
    assert JOB_BOARDS.get("NL")
    names = [b["name"] for b in get_boards_for_country("NL")]
    assert "Indeed NL" in names


def test_ogni_paese_del_menu_ha_portali():
    for c in geo.countries():
        assert JOB_BOARDS.get(c["code"]), f"{c['code']} senza portali in JOB_BOARDS"


def test_sede_olandese_riconosciuta_in_piu_lingue():
    for loc in ("Amsterdam, Netherlands", "Utrecht, Nederland",
                "Rotterdam, Olanda", "Eindhoven, Paesi Bassi"):
        assert country_code(loc) == "NL", loc
