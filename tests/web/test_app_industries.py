from tests.web.conftest import follow


def test_location_page_lists_industries_with_links(client):
    page = client.get("/locations/LEW").text
    assert "Industries" in page and "/locations/LEW/industries/LEW-GRAIN" in page
    assert "/locations/LEW/industries/new" in page
    assert "Apply this location first" in client.get("/locations/new").text


def test_add_edit_and_remove_an_industry(client):
    response = client.post("/locations/LEW/industries/new", data={
        "name": "Lewistown Cement Co.", "track": "2", "car_capacity": "2", "ships": ["grain"], "receives": ["coal"]})
    assert "Applied industry LEW-LEWIST" in follow(client, response).text              # id generated from the name
    assert "Lewistown Cement Co." in client.get("/locations/LEW").text
    page = client.get("/locations/LEW/industries/LEW-LEWIST").text
    assert "data-picker" in page and "readonly" in page
    follow(client, client.post("/locations/LEW/industries/LEW-LEWIST",
                               data={"name": "Lewistown Cement", "track": "2", "car_capacity": "3", "ships": ["grain"]}))
    assert "Lewistown Cement<" in client.get("/locations/LEW").text
    assert "Removed industry LEW-LEWIST" in follow(client, client.post("/locations/LEW/industries/LEW-LEWIST/delete")).text


def test_industry_validation_and_duplicates(client):
    response = client.post("/locations/LEW/industries/new", data={"track": "1"})
    assert response.status_code == 422 and "Required" in response.text
    response = client.post("/locations/LEW/industries/new", data={"id": "ALT-SHOP", "name": "Dup"})
    assert response.status_code == 422 and "Already exists" in response.text


def test_removing_an_industry_that_waybills_use_is_blocked(client):
    response = client.post("/locations/LEW/industries/LEW-GRAIN/delete")             # shipper on waybill-1
    assert "/industries/LEW-GRAIN?flash=" in response.headers["location"]
    assert "waybill-1" in follow(client, response).text


def test_unknown_location_or_industry_is_404(client):
    assert client.get("/locations/NOPE/industries/new").status_code == 404
    assert client.get("/locations/LEW/industries/NOPE").status_code == 404
    assert client.post("/locations/NOPE/industries/new", data={"name": "X"}).status_code == 404


def test_post_to_unknown_industry_is_404_not_create(client):
    # POST to non-existent iid should 404, not create a new industry
    response = client.post("/locations/LEW/industries/NOPE", data={"name": "Bad"})
    assert response.status_code == 404
    # Verify NOPE was not created under LEW
    page = client.get("/locations/LEW").text
    assert "NOPE" not in page


def test_post_to_foreign_industry_is_404(client):
    # POST to ALT-SHOP under LEW should 404 (ALT-SHOP belongs to ALT)
    response = client.post("/locations/LEW/industries/ALT-SHOP", data={"name": "Wrong", "track": "1"})
    assert response.status_code == 404
    # Verify ALT-SHOP is not listed under LEW
    page = client.get("/locations/LEW").text
    assert "/locations/LEW/industries/ALT-SHOP" not in page


def test_delete_unknown_location_is_404(client):
    response = client.post("/locations/NOPE/industries/NOPE/delete")
    assert response.status_code == 404


def test_delete_unknown_industry_is_404(client):
    response = client.post("/locations/LEW/industries/NOPE/delete")
    assert response.status_code == 404


def test_delete_foreign_industry_is_404(client):
    # DELETE /locations/LEW/industries/ALT-SHOP should 404 (belongs to ALT)
    response = client.post("/locations/LEW/industries/ALT-SHOP/delete")
    assert response.status_code == 404
    # Verify ALT-SHOP still exists under ALT
    page = client.get("/locations/ALT/industries/ALT-SHOP").text
    assert "data-picker" in page


def test_new_industry_ids_must_be_url_safe(client):
    for bad_id in ("a#b", "new", "a?b"):
        response = client.post("/locations/LEW/industries/new", data={"id": bad_id, "name": "Bad"})
        assert response.status_code == 422 and "Use only letters, digits" in response.text
    assert "Bad" not in client.get("/locations/LEW").text
    response = client.post("/locations/LEW/industries/new", data={"id": "LEW.ok_1-x", "name": "Fine"})
    assert "Applied industry LEW.ok_1-x" in follow(client, response).text
    assert client.get("/locations/LEW/industries/LEW.ok_1-x").status_code == 200


def test_industry_suggest_id_follows_the_name_and_is_url_safe(client):
    assert client.get("/locations/LEW/industries/suggest-id?name=Lewistown%20Cement%20Co.").json() == {"id": "LEW-LEWIST"}
    assert client.get("/locations/LEW/industries/suggest-id?name=Bob's%20Mill").json() == {"id": "LEW-BOBS"}
    assert client.get("/locations/LEW/industries/suggest-id?name=").json() == {"id": ""}
    assert client.get("/locations/NOPE/industries/suggest-id?name=x").status_code == 404


def test_the_new_industry_form_has_a_locked_id_wired_to_its_suggest_route(client):
    page = client.get("/locations/LEW/industries/new").text
    assert 'data-suggest-url="/locations/LEW/industries/suggest-id"' in page
    assert 'class="locked"' in page and "id-toggle" in page
    existing = client.get("/locations/LEW/industries/LEW-GRAIN").text
    assert "id-toggle" not in existing and "readonly" in existing


def test_a_manual_industry_id_stays_editable_after_an_error(client):
    response = client.post("/locations/LEW/industries/new", data={"id": "MY-IND", "id_manual": "1", "track": "1"})
    assert response.status_code == 422
    assert 'name="id_manual" value="1"' in response.text and 'value="MY-IND"' in response.text
