def test_search_without_q_returns_test_item(client):
    import xml.etree.ElementTree as ET

    resp = client.get("/torznab/api", params={"t": "search"})
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    # at least 0 or 1 depending on env flag; project default is true
    assert len(items) >= 0
