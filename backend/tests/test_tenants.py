from fastapi.testclient import TestClient


def test_create_tenant(client: TestClient) -> None:
    payload = {
        "name": "AutoCorp",
        "industry": "automotive",
        "description": "IATF 16949 certified manufacturer",
    }
    response = client.post("/api/v1/tenants/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "AutoCorp"
    assert data["industry"] == "automotive"
    assert data["is_active"] is True
    assert "id" in data


def test_list_tenants(client: TestClient) -> None:
    client.post("/api/v1/tenants/", json={"name": "Tenant A", "industry": "automotive"})
    client.post("/api/v1/tenants/", json={"name": "Tenant B", "industry": "pharmaceutical"})
    response = client.get("/api/v1/tenants/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_tenant(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/tenants/", json={"name": "GetMe", "industry": "automotive"}
    )
    tenant_id = create_resp.json()["id"]
    response = client.get(f"/api/v1/tenants/{tenant_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "GetMe"


def test_get_tenant_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/tenants/nonexistent-id")
    assert response.status_code == 404


def test_update_tenant(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/tenants/", json={"name": "Original", "industry": "automotive"}
    )
    tenant_id = create_resp.json()["id"]
    response = client.patch(
        f"/api/v1/tenants/{tenant_id}", json={"name": "Updated"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert response.json()["industry"] == "automotive"


def test_delete_tenant(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/tenants/", json={"name": "DeleteMe", "industry": "pharmaceutical"}
    )
    tenant_id = create_resp.json()["id"]
    response = client.delete(f"/api/v1/tenants/{tenant_id}")
    assert response.status_code == 204
    get_resp = client.get(f"/api/v1/tenants/{tenant_id}")
    assert get_resp.status_code == 404
