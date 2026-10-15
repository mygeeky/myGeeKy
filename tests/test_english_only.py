"""Jobs, funding and conferences reach people in English, whatever language the board was in."""

from datetime import date

from mygeeky import curated, scout


def test_a_french_listing_is_not_kept():
    assert not curated.english_enough("Stage M2 : Analyse de données multi-omiques pour la résilience")
    assert not curated.english_enough("Ingénieur de recherche en bioinformatique au LBBE (Lyon)")
    assert not curated.english_enough("Offre de thèse en bioinformatique structurale")


def test_german_spanish_and_italian_are_not_kept():
    assert not curated.english_enough("Doktorand*in (m/w/d) für Bioinformatik am Institut für Genomik")
    assert not curated.english_enough("Convocatoria de plazas para investigación en bioinformática")
    assert not curated.english_enough("Borsa di ricerca per analisi di dati genomici")


def test_english_is_kept_even_with_a_foreign_name_in_it():
    """A post in English at a French institute is in English -- the place name doesn't change that."""
    assert curated.english_enough("Postdoc in statistical genetics, Université de Paris")
    assert curated.english_enough("PhD position: machine learning for single-cell data at ETH Zürich")
    assert curated.english_enough("Lecturer in Computational Biology, £45,000 per annum, Institut de Biologie")


def test_a_short_english_title_is_not_dropped_for_being_short():
    """Nothing marks either language here, so it is taken as English rather than thrown away."""
    assert curated.english_enough("Computational Biologist")
    assert curated.english_enough("Explainable AI for Protein Language Models")


def test_nothing_at_all_is_not_english():
    assert not curated.english_enough("")
    assert not curated.english_enough(None)


def _job(title, **more):
    return {"id": "lab-a-post-2026", "title": title, "url": "https://example.org/1",
            "deadline": "2026-12-01", "org": "A Lab", **more}


def test_the_list_itself_refuses_a_listing_that_is_not_in_english():
    """Every route in goes through clean_item, so this holds for the scout, the curated file and anyone else."""
    assert curated.clean_item("jobs", _job("Offre de poste en bioinformatique dans le laboratoire")) is None
    assert curated.clean_item("funding", _job("Appel à projets pour la recherche en génomique")) is None
    kept = curated.clean_item("jobs", _job("Postdoc in statistical genetics"))
    assert kept and kept["title"] == "Postdoc in statistical genetics"


def test_a_resource_is_not_judged_by_language():
    """Only the dated lists are filtered; a learning resource may be whatever it is."""
    res = curated.clean_item("resources", {"id": "fr-course-2026", "title": "Cours de bioinformatique",
                                           "url": "https://example.org/c"})
    assert res is not None


FRENCH_PAGE = ("Ingénieur de recherche en bioinformatique au LBBE. "
               "Limite de candidature : 1 décembre 2026. Le poste est basé à Lyon.")


def _french(**more):
    """What DeepSeek sends back for a French page: the page's own words, plus the English."""
    return {"is_listing": True, "title": "Ingénieur de recherche en bioinformatique au LBBE",
            "language": "French", "title_en": "Research engineer in bioinformatics at the LBBE",
            "summary_en": "A research engineer post in comparative genomics, based in Lyon.",
            "deadline": "2026-12-01", "deadline_quote": "Limite de candidature : 1 décembre 2026",
            "relevance": 0.9, "confidence": 0.9, **more}


def test_a_french_listing_is_translated_rather_than_dropped():
    out = scout.check("jobs", _french(), {"text": FRENCH_PAGE, "url": "https://www.sfbi.fr/x"},
                      "https://www.sfbi.fr/en/emplois", date(2026, 10, 15))
    assert out["hard_fail"] == "" and out["score"] > 0
    assert any("translated from French" in text for _, text in out["checks"])


def test_the_checks_still_run_against_the_page_in_its_own_language():
    """The French title and the French deadline sentence are what is held against the page."""
    out = scout.check("jobs", _french(), {"text": FRENCH_PAGE, "url": "https://www.sfbi.fr/x"},
                      "https://www.sfbi.fr/en/emplois", date(2026, 10, 15))
    assert dict((text, ok) for ok, text in out["checks"])["title is on the page"]
    assert dict((text, ok) for ok, text in out["checks"])["deadline sentence is on the page"]
    invented = scout.check("jobs", _french(deadline_quote="Applications close on 1 December 2026"),
                           {"text": FRENCH_PAGE, "url": "https://www.sfbi.fr/x"},
                           "https://www.sfbi.fr/en/emplois", date(2026, 10, 15))
    assert not dict((t, ok) for ok, t in invented["checks"])["deadline sentence is on the page"],         "a quote that is not on the page fails, translated or not"


def test_what_is_kept_is_the_english_with_the_original_beside_it():
    item = scout.to_item("jobs", _french(org="LBBE"), "https://www.sfbi.fr/x")
    assert item["title"] == "Research engineer in bioinformatics at the LBBE"
    assert item["original_title"] == "Ingénieur de recherche en bioinformatique au LBBE"
    assert item["language"] == "French"


def test_an_english_listing_is_not_marked_as_translated():
    ans = {"is_listing": True, "title": "Computational Biologist", "title_en": "Computational Biologist",
           "language": "English", "deadline": "2026-12-01", "org": "A Lab",
           "deadline_quote": "Applications close on 1 December 2026", "relevance": 0.9, "confidence": 0.9}
    item = scout.to_item("jobs", ans, "https://example.org/x")
    assert not item.get("original_title") and not item.get("language")


def test_a_listing_with_no_translation_at_all_is_dropped():
    """DeepSeek must send the English back; myGeeKy does not publish what it cannot show in English."""
    ans = _french(title_en="", summary_en="")
    out = scout.check("jobs", ans, {"text": FRENCH_PAGE, "url": "https://sfbi.fr/x"},
                      "https://sfbi.fr", date(2026, 10, 15))
    assert out["hard_fail"] == "no English translation came back"


def test_an_english_listing_on_a_french_board_still_passes_the_language_check():
    page = ("Explainable AI for Protein Language Models. Applications close on 1 December 2026. "
            "The position is based in Lyon.")
    ans = {"is_listing": True, "title": "Explainable AI for Protein Language Models",
           "deadline": "2026-12-01", "deadline_quote": "Applications close on 1 December 2026",
           "relevance": 0.9, "confidence": 0.9}
    out = scout.check("jobs", ans, {"text": page, "url": "https://www.sfbi.fr/x"},
                      "https://www.sfbi.fr/en/emplois/offres-en-cours", date(2026, 10, 15))
    assert out["hard_fail"] == "" and out["score"] > 0
