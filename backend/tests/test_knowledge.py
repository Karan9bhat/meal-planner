"""Knowledge base: place matching, diet rules (and graph/local agreement), dish lookups."""

import pytest

from app import graph, kb

PLACES = [
    ("Pune", "west_indian"), ("Mumbai", "west_indian"), ("Delhi", "north_indian"), ("New Delhi, India", "north_indian"),
    ("Baramulla", "kashmiri"), ("Srinagar", "kashmiri"), ("Chennai", "south_indian"), ("Bengaluru", "south_indian"),
    ("Kolkata", "east_indian"), ("London", "british"), ("Manchester, UK", "british"), ("Edinburgh", "british"),
    ("Lyon", "french"), ("Paris, France", "french"), ("Moscow", "russian"), ("Москва", "russian"),
    ("Rome", "italian"), ("Milano", "italian"), ("Munich", "german"), ("München", "german"), ("Berlin", "german"),
    ("New York", "american"), ("San Francisco", "american"), ("Mexico City", "mexican"), ("Guadalajara", "mexican"),
    ("Shanghai", "chinese"), ("Tokyo, Japan", "japanese"), ("Osaka", "japanese"),
]


@pytest.mark.parametrize("place,cuisine", PLACES)
def test_place_matches_cuisine(place, cuisine):
    hit = kb.match_location(place)
    assert hit and hit[0] == cuisine


@pytest.mark.parametrize("place", ["Columbus", "Kraków", "Nairobi", "xyz123"])
def test_unknown_places_are_not_guessed_locally(place):
    # These must go to the model (or fail), never to a wrong curated cuisine.
    hit = kb.match_location(place)
    assert hit is None or kb.CUISINES[hit[0]].source != "curated"


def dishes_for(cuisine: str, diet: str, restrictions=(), allergies=()):
    banned = kb.excluded_tags_local(diet, list(restrictions), list(allergies))
    return [d for d in kb.CUISINES[cuisine].dishes if not banned & set(d.contains)]


@pytest.mark.parametrize("cuisine", [k for k, p in kb.CUISINES.items() if p.source == "curated"])
def test_vegan_never_gets_animal_products(cuisine):
    for d in dishes_for(cuisine, "vegan"):
        assert not {"dairy", "egg", "poultry", "beef", "pork", "lamb_mutton", "fish", "shellfish"} & set(d.contains), d.name


def test_rules_compose():
    halal_veg_peanut = kb.excluded_tags_local("pescatarian", ["halal"], ["peanut"])
    assert {"pork", "beef", "poultry", "lamb_mutton", "alcohol", "peanut"} <= halal_veg_peanut
    assert "fish" not in halal_veg_peanut


def test_jain_excludes_roots_and_alliums():
    names = {d.name for d in dishes_for("north_indian", "jain")}
    assert "Samosa" not in names and "Aloo paratha" not in names and "Dal tadka" not in names


def test_custom_allergy_is_a_banned_word():
    assert "kiwi" in kb.excluded_tags_local("omnivore", [], ["kiwi"])


@pytest.mark.skipif(not graph.available(), reason="MongoDB knowledge graph not configured")
@pytest.mark.parametrize("diet", list(kb.DIET_TYPES))
def test_graph_rules_match_local_rules(diet):
    for restrictions, allergies in [((), ()), (("halal",), ("peanut",)), (("kosher", "no_alcohol"), ("dairy", "gluten"))]:
        g = graph.excluded_tags(diet, list(restrictions), list(allergies))
        local = kb.excluded_tags_local(diet, list(restrictions), list(allergies))
        assert g == local, (diet, restrictions, allergies)


@pytest.mark.skipif(not graph.available(), reason="MongoDB knowledge graph not configured")
def test_graph_dish_traversal_matches_memory():
    banned = kb.excluded_tags_local("vegetarian", [], ["gluten"])
    from_graph = {d.name for d in graph.allowed_dishes(["french"], banned)}
    in_memory = {d.name for d in kb.reference_dishes(["french"], banned)}
    assert from_graph == in_memory


def test_mentioned_dishes_finds_named_food():
    names = [d["name"] for d in kb.mentioned_dishes("chai and poha, dal rice and roti", ["west_indian"], limit=10)]
    assert "Poha" in names and "Roti / chapati" in names
