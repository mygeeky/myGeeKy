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


def test_the_scout_says_why_it_dropped_one():
    ans = {"is_listing": True, "title": "Ingénieur de recherche en bioinformatique au LBBE",
           "deadline": "2026-12-01", "deadline_quote": "Limite de candidature : 1 décembre 2026",
           "relevance": 0.9, "confidence": 0.9}
    out = scout.check("jobs", ans, {"text": "", "url": "https://sfbi.fr/x"}, "https://sfbi.fr", date(2026, 10, 15))
    assert out["hard_fail"] == "not in English"


def test_an_english_listing_on_a_french_board_still_passes_the_language_check():
    page = ("Explainable AI for Protein Language Models. Applications close on 1 December 2026. "
            "The position is based in Lyon.")
    ans = {"is_listing": True, "title": "Explainable AI for Protein Language Models",
           "deadline": "2026-12-01", "deadline_quote": "Applications close on 1 December 2026",
           "relevance": 0.9, "confidence": 0.9}
    out = scout.check("jobs", ans, {"text": page, "url": "https://www.sfbi.fr/x"},
                      "https://www.sfbi.fr/en/emplois/offres-en-cours", date(2026, 10, 15))
    assert out["hard_fail"] == "" and out["score"] > 0
