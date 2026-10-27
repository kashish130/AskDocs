from pathlib import Path

import pytest

from app.config import settings

pytestmark = pytest.mark.anyio


async def test_upload_happy_path(client, login_as):
    headers = await login_as("user@example.com")
    org = (await client.post("/orgs", json={"name": "Alchemist"}, headers=headers)).json()
    resp = await client.post(
        f"/orgs/{org['id']}/documents",
        headers=headers,
        files={"file": ("test.pdf", b"%PDF-1.4\n...", "application/pdf")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "test.pdf"
    assert body["status"] == "queued"
    assert "storage_key" not in body


async def test_duplicate_file_rejects(client, login_as):
    pdf_bytes = b"%PDF-1.4\nsome content"
    file_payload = ("doc.pdf", pdf_bytes, "application/pdf")
    headers = await login_as("user1@example.com")
    org = (await client.post("/orgs", json={"name": "Alchemist"}, headers=headers)).json()
    first = await client.post(
        f"/orgs/{org['id']}/documents",
        headers=headers,
        files={"file": file_payload},
    )

    assert first.status_code == 201
    # ---second upload of the same file should be rejected---
    second = await client.post(
        f"/orgs/{org['id']}/documents",
        headers=headers,
        files={"file": file_payload},
    )

    assert second.status_code == 409

    # Stretch : prove exactly one file sits in the database for this org
    org_dir = Path(settings.storage_dir) / org["id"]
    files = list(org_dir.iterdir())
    assert len(files) == 1


async def test_upload_same_file_different_org(client, login_as):
    pdf_bytes = b"%PDF-1.4\nhello world"
    file_payload = ("doc.pdf", pdf_bytes, "application/pdf")

    # --- Organization 1 uploads the file ---
    headers_a = await login_as("alice@example.com")
    org1 = (await client.post("/orgs", json={"name": "Org A"}, headers=headers_a)).json()
    resp_a = await client.post(
        f"/orgs/{org1['id']}/documents",
        headers=headers_a,
        files={"file": file_payload},
    )
    assert resp_a.status_code == 201

    # --- Organization 2 uploads the same file ---
    headers_b = await login_as("bob@example.com")
    org2 = (await client.post("/orgs", json={"name": "Org B"}, headers=headers_b)).json()
    resp_b = await client.post(
        f"/orgs/{org2['id']}/documents",
        headers=headers_b,
        files={"file": file_payload},
    )
    assert resp_b.status_code == 201


async def test_upload_rejects_bad_mime(client, login_as):
    headers = await login_as("alice@example.com")
    org = (await client.post("/orgs", json={"name": "Marriot"}, headers=headers)).json()

    resp = await client.post(
        f"/orgs/{org['id']}/documents",
        headers=headers,
        files={"file": ("Learning.png", b"\x89PNG\r\n\x1a\n...", "image/png")},
    )
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]


async def test_upload_rejects_too_large(client, login_as):
    headers = await login_as("bob@example.com")
    org = (await client.post("/orgs", json={"name": "Marriot"}, headers=headers)).json()

    # Create a file that is too large (assuming the limit is 10MB)
    large_file = b"x" * (26 * 1024 * 1024)  # 26MB of data
    resp = await client.post(
        f"/orgs/{org['id']}/documents",
        headers=headers,
        files={"file": ("large.pdf", large_file, "application/pdf")},
    )
    assert resp.status_code == 413
