"""A listing can be read in other languages. English stays the record; a translation never changes it."""

from datetime import date

from mygeeky import curated, scout

AR = {"title": "مهندس بحث في المعلوماتية الحيوية", "summary": "وظيفة مهندس بحث في ليون."}
FR = {"title": "Ingénieur de recherche en bioinformatique", "summary": "Un poste d'ingénieur à Lyon."}
ZH = {"title": "生物信息学研究工程师", "summary": "位于里昂的研究工程师职位。"}


def test_the_five_languages_bring_their_own_names_and_direction():
    said = curated.clean_translations({"ar": AR, "fr": FR, "zh": ZH})
    assert said["ar"]["name"] == "العربية" and said["ar"]["rtl"] is True
    assert said["fr"]["name"] == "Français" and said["fr"]["rtl"] is False
    assert said["zh"]["name"] == "中文" and said["zh"]["rtl"] is False
    assert said["ar"]["title"] == AR["title"]


def test_a_language_myGeeKy_has_never_heard_of_still_works():
    """This is the point of carrying the name in the data: a language can be added to the lists alone,
    and reach everyone within hours, without anyone installing a new myGeeKy."""
    said = curated.clean_translations({"it": {"name": "Italiano", "title": "Ingegnere di ricerca"}})
    assert said["it"]["name"] == "Italiano" and said["it"]["title"] == "Ingegnere di ricerca"
    assert said["it"]["rtl"] is False


def test_a_language_with_no_name_at_all_is_left_out():
    """Nothing could be written on the button, so there is nothing to offer."""
    assert curated.clean_translations({"zz": {"title": "something"}}) == {}


def test_a_translation_with_no_title_is_left_out():
    assert curated.clean_translations({"fr": {"summary": "seulement un résumé"}}) == {}


def test_rubbish_in_the_translations_block_is_simply_ignored():
    for bad in (None, "", [], 7, {"fr": "not a dict"}, {"français": {"title": "x"}}):
        assert curated.clean_translations(bad) == {}


def _job(**more):
    return {"id": "lbbe-research-engineer-2026", "title": "Research engineer in bioinformatics",
            "url": "https://example.org/1", "deadline": "2026-12-01", "org": "LBBE",
            "summary": "A research engineer post in comparative genomics.", **more}


def test_a_bad_translation_never_costs_the_listing_itself():
    """A translation is a reading aid. Whatever is wrong with it, the English listing still stands."""
    for bad in (None, "nonsense", {"zz": {"title": "x"}}, {}):
        kept = curated.clean_item("jobs", _job(translations=bad))
        assert kept and kept["title"] == "Research engineer in bioinformatics"
        assert "translations" not in kept


def test_the_lists_keep_the_translations_for_jobs_funding_and_conferences():
    for kind in ("jobs", "funding", "conferences"):
        kept = curated.clean_item(kind, _job(translations={"ar": AR, "zh": ZH}))
        assert sorted(kept["translations"]) == ["ar", "zh"]


def test_a_resource_carries_no_translations():
    """Only the dated lists are translated: that is what people are choosing between under a deadline."""
    kept = curated.clean_item("resources", {"id": "a-course-2026", "title": "A course",
                                            "url": "https://example.org/c", "translations": {"fr": FR}})
    assert kept is not None and "translations" not in kept


def test_the_languages_are_offered_in_a_settled_order():
    """Known languages first, in myGeeKy's own order, so the button reads the same on every card."""
    it = {"translations": curated.clean_translations({"zh": ZH, "ar": AR, "fr": FR,
                                                      "it": {"name": "Italiano", "title": "Ingegnere"}})}
    assert curated.languages_of(it) == ["ar", "fr", "zh", "it"]


def test_a_listing_with_no_translations_offers_nothing():
    assert curated.languages_of({}) == [] and curated.languages_of({"translations": {}}) == []


PAGE = ("Ingénieur de recherche en bioinformatique au LBBE. "
        "Limite de candidature : 1 décembre 2026. Le poste est basé à Lyon.")


def _answer(**more):
    return {"is_listing": True, "title": "Ingénieur de recherche en bioinformatique au LBBE",
            "language": "French", "title_en": "Research engineer in bioinformatics at the LBBE",
            "summary_en": "A research engineer post in comparative genomics, based in Lyon.",
            "org": "LBBE", "deadline": "2026-12-01",
            "deadline_quote": "Limite de candidature : 1 décembre 2026",
            "translations": {"ar": AR, "fr": FR, "zh": ZH}, "relevance": 0.9, "confidence": 0.9, **more}


def test_what_the_scout_keeps_is_the_english_with_every_language_beside_it():
    item = scout.to_item("jobs", _answer(), "https://www.sfbi.fr/x")
    assert item["title"] == "Research engineer in bioinformatics at the LBBE"
    assert item["original_title"].startswith("Ingénieur") and item["language"] == "French"
    assert curated.languages_of(item) == ["ar", "fr", "zh"]


def test_a_missing_translations_block_does_not_hurt_the_score():
    """Nothing about a translation can fail a listing: it is not evidence, so it is not checked."""
    with_them = scout.check("jobs", _answer(), {"text": PAGE, "url": "https://www.sfbi.fr/x"},
                            "https://www.sfbi.fr/en/emplois", date(2026, 10, 15))
    without = scout.check("jobs", _answer(translations=None), {"text": PAGE, "url": "https://www.sfbi.fr/x"},
                          "https://www.sfbi.fr/en/emplois", date(2026, 10, 15))
    assert with_them["hard_fail"] == "" and without["hard_fail"] == ""
    assert with_them["score"] == without["score"]


def test_a_translated_listing_that_matches_no_part_of_its_page_is_still_refused():
    """The guard used to read the first check in the list, which a translated listing had taken over --
    so an invented French listing could pass with neither its title nor its deadline on the page."""
    out = scout.check("jobs", _answer(title="Poste inventé qui n'existe pas", title_en="An invented post",
                                      deadline_quote="Une phrase qui n'est pas sur la page"),
                      {"text": PAGE, "url": "https://www.sfbi.fr/x"},
                      "https://www.sfbi.fr/en/emplois", date(2026, 10, 15))
    assert out["hard_fail"] == "neither the title nor the deadline could be found on the page"


# --------------------------------------------------------------------------- inside the card, not a window
def test_the_translation_opens_inside_the_card(qapp_offscreen):
    """myGeeKy is docked to the side of the screen: a window of its own has nowhere to go, so the card
    grows instead. It starts closed, opens on the first press and closes again on the next."""
    from PySide6.QtWidgets import QPushButton
    from mygeeky.gui.growth_ui import OpportunityCard, SaidPanel
    from mygeeky.gui.qt_panel import THEMES
    it = curated.clean_item("jobs", _job(translations={"ar": AR, "fr": FR, "zh": ZH}))
    card = OpportunityCard("jobs", dict(it, days_left=47), THEMES["midnight"], lambda up: 0, lambda u: None,
                           lambda k, i: None)
    panels = card.findChildren(SaidPanel)
    assert len(panels) == 1, "the card carries its own translation panel"
    said = panels[0]
    assert said.isHidden(), "it starts closed, so a card stays the size it was"
    rows = [b for b in card.findChildren(QPushButton) if b.text().startswith("🌍")]
    assert len(rows) == 1 and "العربية" in rows[0].text(), "the row names the languages in their own scripts"
    assert rows[0].text().endswith("▾"), "the caret says the row is a switch"
    rows[0].click()
    assert not said.isHidden(), "pressing it opens the translation in the card"
    assert rows[0].text().endswith("▴"), "and the caret turns round"
    rows[0].click()
    assert said.isHidden(), "pressing it again closes it"


def test_the_translation_can_be_closed_from_inside_itself(qapp_offscreen):
    """Someone who has read down the translation should not have to scroll back up to the row."""
    from PySide6.QtWidgets import QPushButton
    from mygeeky.gui.growth_ui import OpportunityCard, SaidPanel
    from mygeeky.gui.qt_panel import THEMES
    it = curated.clean_item("jobs", _job(translations={"ar": AR, "fr": FR, "zh": ZH}))
    card = OpportunityCard("jobs", dict(it, days_left=47), THEMES["midnight"], lambda up: 0, lambda u: None,
                           lambda k, i: None)
    said = card.findChildren(SaidPanel)[0]
    row = [b for b in card.findChildren(QPushButton) if b.text().startswith("🌍")][0]
    row.click()
    assert not said.isHidden()
    shut = [b for b in said.findChildren(QPushButton) if b.text() == "✕"]
    assert len(shut) == 1, "the translation carries its own way out"
    shut[0].click()
    assert said.isHidden(), "the cross closes it"
    assert row.text().endswith("▾"), "and the row agrees that it is closed again"


def test_arabic_is_laid_out_right_to_left(qapp_offscreen):
    from PySide6.QtCore import Qt
    from mygeeky.gui.growth_ui import SaidPanel
    from mygeeky.gui.qt_panel import THEMES
    it = curated.clean_item("jobs", _job(translations={"ar": AR, "fr": FR}))
    said = SaidPanel(it, THEMES["midnight"])
    assert said._body.layoutDirection() == Qt.RightToLeft, "Arabic is offered first, and reads right to left"
    said.show_language("fr")
    assert said._body.layoutDirection() == Qt.LeftToRight
    assert FR["title"] in said._body.text()


def test_a_card_with_no_translations_has_no_row(qapp_offscreen):
    from mygeeky.gui.growth_ui import OpportunityCard, SaidPanel
    from mygeeky.gui.qt_panel import THEMES
    it = curated.clean_item("jobs", _job())
    card = OpportunityCard("jobs", dict(it, days_left=47), THEMES["midnight"], lambda up: 0, lambda u: None,
                           lambda k, i: None)
    assert card.findChildren(SaidPanel) == []
