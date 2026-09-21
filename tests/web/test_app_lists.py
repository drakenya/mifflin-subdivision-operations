def test_static_assets_are_served_from_the_package(client):
    for name in ("htmx.min.js", "tom-select.complete.min.js", "tom-select.default.min.css", "app.css"):
        assert client.get(f"/static/{name}").status_code == 200, name


def test_home_redirects_to_waybills(client):
    response = client.get("/")
    assert response.status_code == 303 and response.headers["location"] == "/waybills"


def test_waybill_list_shows_a_readable_summary_per_type(client):
    page = client.get("/waybills").text
    assert "Grain: Lewistown Grain Elevator → Altoona Shops" in page       # LOADED
    assert "Altoona → Lewistown" in page                                    # EMPTY
    assert "Lewistown → shop Altoona: Broken coupler" in page               # BAD_ORDER
    assert "PHL → PGH" in page                                              # DEADHEAD with unknown locations
    assert "Lewistown Grain Elevator waiting for Load order" in page        # HOLD
    assert "6 shown of 6" in page


def test_every_collection_lists(client):
    for kind, expected in [("cars", "PRR-12345"), ("locations", "Lewistown"), ("commodities", "Bituminous"),
                           ("railroads", "Form 1304")]:
        page = client.get(f"/{kind}").text
        assert expected in page, kind
        assert f'href="/{kind}/new"' in page


def test_search_and_type_filter(client):
    assert "badorder-1" not in client.get("/waybills?q=grain").text
    filtered = client.get("/waybills?type=BAD_ORDER").text
    assert "badorder-1" in filtered and "1 shown of 6" in filtered
    assert "No matches." in client.get("/cars?q=zzz").text


def test_unknown_collection_or_record_is_404(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/cars/NOPE").status_code == 404


def test_nav_lists_all_collections_and_hides_unsaved_banner_when_clean(client):
    page = client.get("/cars").text
    for title in ("Waybills", "Cars", "Locations", "Commodities", "Railroads"):
        assert f">{title}</a>" in page
    assert "unsaved" not in page
