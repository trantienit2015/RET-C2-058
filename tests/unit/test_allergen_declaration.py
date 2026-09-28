from src.services.allergen_declaration import (
    MAX_TEXT_CHARS,
    canonical_allergen,
    merge_declared_allergens,
    parse_declared_allergens,
)


class TestParseDeclaredAllergens:
    def test_avoid_cue(self):
        assert parse_declared_allergens("Plan 3 dinners that are high in protein and avoid shellfish") == ["shellfish"]

    def test_member_terms_map_to_canonical(self):
        assert parse_declared_allergens("no fish or shrimp please") == ["fish", "shellfish"]

    def test_free_suffix(self):
        assert parse_declared_allergens("nut-free and dairy free dinner") == ["tree nut", "milk"]

    def test_allergic_to_stops_at_clause_connector(self):
        assert parse_declared_allergens("I am allergic to eggs, but I like salmon") == ["egg"]

    def test_positive_mentions_are_not_avoidances(self):
        assert parse_declared_allergens("Plan dinners with salmon and shrimp") == []
        assert parse_declared_allergens("high protein meals, no spicy food") == []

    def test_non_string_and_empty(self):
        assert parse_declared_allergens(None) == []
        assert parse_declared_allergens("") == []

    def test_input_is_bounded(self):
        text = "x " * MAX_TEXT_CHARS + "avoid shellfish"
        assert parse_declared_allergens(text) == []


class TestMerge:
    def test_merge_dedupes_and_canonicalises(self):
        assert merge_declared_allergens(["Shellfish", "dairy"], "avoid shrimp and eggs") == ["shellfish", "milk", "egg"]

    def test_unknown_context_value_kept_lowercase(self):
        assert canonical_allergen(" Mustard ") == "mustard"
        assert merge_declared_allergens("not-a-list", "") == []
