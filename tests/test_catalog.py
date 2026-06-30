import pytest
from pathlib import Path
from pydantic import ValidationError
from waybill_generator.models.catalog import CatalogIndustry
from waybill_generator.repository.catalog_repo import CatalogRepository

FIXTURES = Path(__file__).parent / "fixtures"


class TestCatalogIndustry:
    def test_basic_construction(self):
        entry = CatalogIndustry(
            id="cat-001",
            name="Clearfield Coal & Coke Co.",
            city="Clearfield",
            source="opsig",
            source_file="coal-mines-pa.csv",
            source_ref="OPSIG-4872",
            ships=["coal"],
            car_types=["HM", "HT"],
        )
        assert entry.state == "PA"
        assert entry.receives == []
        assert entry.notes is None
        assert entry.railroad_id is None

    def test_all_optional_fields(self):
        entry = CatalogIndustry(
            id="cat-x", name="Test Industry", city="Testville",
            source="manual", source_file="manual",
        )
        assert entry.state == "PA"
        assert entry.railroad_id is None
        assert entry.source_ref is None
        assert entry.ships == []
        assert entry.receives == []
        assert entry.car_types == []
        assert entry.notes is None

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            # missing source and source_file
            CatalogIndustry(id="x", name="Test", city="Testville")


@pytest.fixture
def catalog_repo():
    return CatalogRepository(FIXTURES / "industry_catalog.yaml")


class TestCatalogRepository:
    def test_get_by_id(self, catalog_repo):
        entry = catalog_repo.get("cat-001")
        assert entry.name == "Clearfield Coal & Coke Co."

    def test_get_missing_raises(self, catalog_repo):
        with pytest.raises(KeyError):
            catalog_repo.get("MISSING")

    def test_search_no_filters_returns_all(self, catalog_repo):
        results = catalog_repo.search()
        assert len(results) == 3

    def test_search_keyword_name(self, catalog_repo):
        results = catalog_repo.search(keyword="clearfield")
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_keyword_city(self, catalog_repo):
        results = catalog_repo.search(keyword="sunbury")
        assert len(results) == 1
        assert results[0].id == "cat-002"

    def test_search_keyword_notes(self, catalog_repo):
        results = catalog_repo.search(keyword="locomotive")
        assert len(results) == 1
        assert results[0].id == "cat-003"

    def test_search_commodity_ships(self, catalog_repo):
        results = catalog_repo.search(commodity="coal", ships=True)
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_commodity_receives(self, catalog_repo):
        results = catalog_repo.search(commodity="coal", receives=True)
        assert len(results) == 1
        assert results[0].id == "cat-003"

    def test_search_commodity_both_directions(self, catalog_repo):
        results = catalog_repo.search(commodity="coal")
        ids = {e.id for e in results}
        assert "cat-001" in ids
        assert "cat-003" in ids

    def test_search_car_type(self, catalog_repo):
        results = catalog_repo.search(car_type="HM")
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_car_type_case_insensitive(self, catalog_repo):
        results = catalog_repo.search(car_type="hm")
        assert len(results) == 1

    def test_search_railroad(self, catalog_repo):
        results = catalog_repo.search(railroad="PRR")
        assert len(results) == 3

    def test_search_source(self, catalog_repo):
        results = catalog_repo.search(source="opsig")
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_limit(self, catalog_repo):
        results = catalog_repo.search(limit=2)
        assert len(results) == 2

    def test_search_no_match_returns_empty(self, catalog_repo):
        results = catalog_repo.search(keyword="xyznotfound")
        assert results == []
