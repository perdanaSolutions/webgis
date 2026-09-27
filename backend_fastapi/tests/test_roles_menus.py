import uuid


def test_menu_tree(client, auth):
    suffix = uuid.uuid4().hex[:6]
    parent = client.post("/api/v1/menus/", headers=auth, json={"title": f"Induk {suffix}", "icon": "mdi-a", "to": "/induk"}).json()
    child = client.post("/api/v1/menus/", headers=auth,
                        json={"title": f"Anak {suffix}", "icon": "mdi-b", "parent_id": parent["id"]}).json()
    grandchild = client.post("/api/v1/menus/", headers=auth,
                             json={"title": f"Cucu {suffix}", "icon": "mdi-c", "parent_id": child["id"]}).json()
    assert (parent["level"], child["level"], grandchild["level"]) == (1, 2, 3)
    assert parent["to"] == "/induk"

    too_deep = client.post("/api/v1/menus/", headers=auth, json={"title": "x", "icon": "y", "parent_id": grandchild["id"]})
    assert too_deep.status_code == 400

    cycle = client.put(f"/api/v1/menus/{parent['id']}", headers=auth, json={"parent_id": grandchild["id"]})
    assert cycle.status_code == 400

    tree = client.get("/api/v1/menus/", headers=auth).json()
    node = next(m for m in tree if m["id"] == parent["id"])
    assert node["children"][0]["children"][0]["id"] == grandchild["id"]

    assert client.delete(f"/api/v1/menus/{parent['id']}", headers=auth).status_code == 400  # masih punya anak
    for menu in (grandchild, child, parent):
        assert client.delete(f"/api/v1/menus/{menu['id']}", headers=auth).status_code == 200


def test_role_with_access(client, auth, sample_block):
    suffix = uuid.uuid4().hex[:6]
    menu = client.post("/api/v1/menus/", headers=auth, json={"title": f"Peta {suffix}", "icon": "mdi-map"}).json()
    tables = client.get("/api/v1/database/tables", headers=auth).json()
    assert "trx.block_productions" in tables

    role = client.post("/api/v1/roles/", headers=auth, json={
        "nama": f"Surveyor {suffix}", "deskripsi": "test",
        "akses_menu": [menu["id"]], "akses_transaksi": ["trx.block_productions"],
    })
    assert role.status_code == 201, role.text
    role = role.json()
    assert role["nama"] == f"surveyor {suffix}"
    assert role["akses_menu"][0]["menu_id"] == menu["id"]
    assert role["akses_transaksi"][0]["nama_table_transaksi"] == "trx.block_productions"

    # idempoten (FE memanggil ulang setelah PUT role)
    again = client.post("/api/v1/akses-data/menu", headers=auth, json={"role_id": role["id"], "menu_id": menu["id"]})
    assert again.status_code == 201

    estates = client.get("/api/v1/spatial/estate", headers=auth, params={"kode_est": sample_block["estate"]}).json()["data"]
    divisions = client.get("/api/v1/spatial/afdeling", headers=auth,
                           params={"kode_est": sample_block["estate"], "kode_afd": sample_block["division"]}).json()["data"]
    tree = [{
        "id_area": "BERAU", "nama_area": "BERAU",
        "perusahaan": [{
            "id_perusahaan": str(estates[0]["pt_id"]), "nama_perusahaan": "x",
            "estate": [{"id_estate": str(estates[0]["id"]), "nama_estate": "x",
                        "afdeling": [{"id_afdeling": str(divisions[0]["id"]), "nama_afdeling": "x"}]}],
        }],
    }]
    added = client.post(f"/api/v1/akses-data/data/role/{role['id']}", headers=auth, json=tree).json()
    assert added["tidak_ditemukan"] == []

    got = client.get(f"/api/v1/akses-data/data/role/{role['id']}", headers=auth).json()
    afd = got[0]["perusahaan"][0]["estate"][0]["afdeling"][0]
    assert afd["id_afdeling"] == str(divisions[0]["id"])

    detail = client.get(f"/api/v1/roles/{role['id']}", headers=auth).json()
    scope = detail["akses_data"][0]
    assert (scope["level"], scope["kode_est"], scope["kode_afd"]) == ("division", sample_block["estate"], sample_block["division"])

    updated = client.put(f"/api/v1/roles/{role['id']}", headers=auth, json={"nama": f"surveyor {suffix}", "akses_menu": []}).json()
    assert updated["akses_menu"] == [] and updated["akses_transaksi"]  # transaksi tidak dikirim -> tetap

    assert client.delete(f"/api/v1/akses-data/data/{scope['id']}", headers=auth).status_code == 200
    assert client.delete(f"/api/v1/roles/{role['id']}", headers=auth).status_code == 200
    client.delete(f"/api/v1/menus/{menu['id']}", headers=auth)


def test_superadmin_role_can_be_edited(client, auth):
    roles = client.get("/api/v1/roles/", headers=auth).json()
    superadmin = next(r for r in roles if r["nama"] == "superadmin")
    original = superadmin.get("deskripsi")
    updated = client.put(
        f"/api/v1/roles/{superadmin['id']}",
        headers=auth,
        json={"nama": "superadmin", "deskripsi": "diubah oleh test"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["nama"] == "superadmin"
    restored = client.put(
        f"/api/v1/roles/{superadmin['id']}",
        headers=auth,
        json={"nama": "superadmin", "deskripsi": original},
    )
    assert restored.status_code == 200


def test_permissions_crud(client, auth):
    suffix = uuid.uuid4().hex[:6]
    created = client.post("/api/v1/permissions/", headers=auth, json={"resource": f"res{suffix}", "aksi": "read"}).json()
    assert created["kode"] == f"res{suffix}:read"
    assert client.delete(f"/api/v1/permissions/{created['id']}", headers=auth).status_code == 200
