from app.triage_rules.category_matching_service import CategoryMatchingService


def test_category_matching_finds_wifi_category() -> None:
    match = CategoryMatchingService().find_best_match("wifi caindo")

    assert match.category_id == 11
    assert match.category_name == "Ubiquiti / Wi-Fi"


def test_category_matching_finds_printer_category() -> None:
    match = CategoryMatchingService().find_best_match("nao consigo imprimir")

    assert match.category_id == 3
    assert match.category_name == "Impressora"

