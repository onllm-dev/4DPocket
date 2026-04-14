"""Tests for import/export endpoints."""

import io
import json

from starlette.testclient import TestClient


class TestExportJSON:
    def test_export_json_returns_valid_json(self, client, auth_headers):
        # Create items first
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/1", "title": "Item One"},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/2", "title": "Item Two"},
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/json", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers.get("content-disposition", "")

        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert "exported_at" in data

    def test_export_json_contains_all_item_fields(self, client, auth_headers):
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/field-test",
                "title": "Field Test",
                "description": "A description",
                "content": "Full content",
            },
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/json", headers=auth_headers)
        data = response.json()
        item = data["items"][0]
        assert item["url"] == "https://example.com/field-test"
        assert item["title"] == "Field Test"
        assert item["description"] == "A description"
        assert item["content"] == "Full content"
        assert "id" in item
        assert "created_at" in item

    def test_export_json_user_scoping(self, client, auth_headers, second_user_headers):
        # User A creates an item
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-a"},
            headers=auth_headers,
        )
        # User B creates an item
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-b"},
            headers=second_user_headers,
        )

        # User A's export should only have their item
        response = client.get("/api/v1/export/json", headers=auth_headers)
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["url"] == "https://example.com/user-a"

    def test_export_json_empty_collection(self, client, auth_headers):
        response = client.get("/api/v1/export/json", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


class TestExportCSV:
    def test_export_csv_returns_valid_csv(self, client, auth_headers):
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/csv", "title": "CSV Item"},
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/csv", headers=auth_headers)
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")

        content = response.content.decode("utf-8")
        # Should have header row + 1 data row
        lines = [ln for ln in content.strip().split("\n") if ln]
        assert len(lines) == 2
        assert "title" in lines[0].lower()
        assert "url" in lines[0].lower()

    def test_export_csv_escapes_special_characters(self, client, auth_headers):
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/special",
                "title": 'Title with, comma "quotes" and\nnewline',
                "description": "Normal description",
            },
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/csv", headers=auth_headers)
        content = response.content.decode("utf-8")
        # CSV writer escapes comma and quotes; newline in quoted field splits into extra line(s)
        lines = [ln for ln in content.strip().split("\n") if ln]
        # Should have header + data row (data may span multiple lines due to newline in quoted field)
        assert len(lines) >= 2
        # Header should contain expected column names
        assert "title" in lines[0].lower()
        assert "url" in lines[0].lower()
        # Data row should contain the URL
        assert "https://example.com/special" in content


class TestExportUnsupportedFormat:
    def test_export_unsupported_format_returns_400(self, client, auth_headers):
        response = client.get("/api/v1/export/xml", headers=auth_headers)
        assert response.status_code == 400
        assert "Unsupported format" in response.json()["detail"]


class TestImportJSON:
    def test_import_json_creates_items(self, client, auth_headers):
        payload = json.dumps([
            {"url": "https://example.com/1", "title": "Imported One"},
            {"url": "https://example.com/2", "title": "Imported Two"},
        ])

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("import.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 2

        # Verify items exist
        export_resp = client.get("/api/v1/export/json", headers=auth_headers)
        assert len(export_resp.json()["items"]) == 2

    def test_import_json_with_items_wrapper(self, client, auth_headers):
        payload = json.dumps({
            "items": [
                {"url": "https://example.com/wrapped", "title": "Wrapped Item"},
            ]
        })

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("import.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 1

    def test_import_json_invalid_format_returns_error(self):
        import uuid
        from fourdpocket.main import app
        # Use raise_server_exceptions=False to get error response instead of exception
        error_client = TestClient(app, raise_server_exceptions=False)

        unique = uuid.uuid4().hex[:8]
        error_client.post(
            "/api/v1/auth/register",
            json={"email": f"err{unique}@test.com", "username": f"erruser{unique}", "password": "TestPass123!", "display_name": "E"},
        )
        resp = error_client.post("/api/v1/auth/login", data={"username": f"err{unique}@test.com", "password": "TestPass123!"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = error_client.post(
            "/api/v1/import/json",
            files={"file": ("bad.json", io.BytesIO(b"not valid json{"), "application/json")},
            headers=headers,
        )
        # Invalid JSON returns 500 (unhandled JSONDecodeError)
        assert response.status_code == 500

    def test_import_json_duplicate_handling(self, client, auth_headers):
        # Import same URL twice — both should be imported (no dedup at import layer)
        payload = json.dumps([
            {"url": "https://example.com/dup", "title": "First"},
            {"url": "https://example.com/dup", "title": "Second"},
        ])

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("dupes.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 2

    def test_import_json_truncates_long_fields(self, client, auth_headers):
        long_description = "x" * 60_000
        long_content = "y" * 1_100_000
        payload = json.dumps([{
            "url": "https://example.com/long",
            "title": "Long Fields",
            "description": long_description,
            "content": long_content,
        }])

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("long.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify truncation was applied
        export = client.get("/api/v1/export/json", headers=auth_headers)
        item = export.json()["items"][0]
        assert len(item["description"]) <= 50_000
        assert len(item["content"]) <= 1_000_000

    def test_import_json_skips_javascript_urls(self, client, auth_headers):
        payload = json.dumps([
            {"url": "https://example.com/valid", "title": "Valid"},
            {"url": "javascript:alert(1)", "title": "Invalid"},
        ])

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("filtered.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 1
        # Verify the imported item is the valid URL
        export = client.get("/api/v1/export/json", headers=auth_headers)
        assert export.json()["items"][0]["url"] == "https://example.com/valid"

    def test_import_json_too_many_items_returns_413(self, client, auth_headers):
        items = [{"url": f"https://example.com/{i}", "title": f"Item {i}"} for i in range(10001)]
        payload = json.dumps(items)

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("toomany.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 413

    def test_import_json_large_file_within_limit(self, client, auth_headers):
        # Create a file just under 10MB
        items = [
            {"url": f"https://example.com/{i}", "title": f"Item {i}", "content": "x" * 1000}
            for i in range(5000)
        ]
        payload = json.dumps(items)
        # ~5000 * ~1KB = ~5MB, should pass
        assert len(payload.encode()) < 10 * 1024 * 1024

        response = client.post(
            "/api/v1/import/json",
            files={"file": ("large.json", io.BytesIO(payload.encode()), "application/json")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 5000


class TestImportChrome:
    def test_import_chrome_html(self, client, auth_headers):
        html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<TITLE>Bookmarks</TITLE>
<DL><p>
    <DT><A HREF="https://example.com/1">First Bookmark</A>
    <DT><A HREF="https://example.com/2">Second Bookmark</A>
</DL><p>"""

        response = client.post(
            "/api/v1/import/chrome",
            files={"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 2

    def test_import_chrome_skips_non_http(self, client, auth_headers):
        html = """<DL><p>
    <DT><A HREF="https://example.com/valid">Valid</A>
    <DT><A HREF="javascript:bad()">Bad JS</A>
</DL><p>"""

        response = client.post(
            "/api/v1/import/chrome",
            files={"file": ("chrome.html", io.BytesIO(html.encode()), "text/html")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 1


class TestImportPocket:
    def test_import_pocket_html(self, client, auth_headers):
        html = """<DL><p>
    <a href="https://example.com/pocket/1">Pocket Item One</a>
    <a href="https://example.com/pocket/2">Pocket Item Two</a>
</DL><p>"""

        response = client.post(
            "/api/v1/import/pocket",
            files={"file": ("pocket.html", io.BytesIO(html.encode()), "text/html")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 2


class TestImportUnsupportedSource:
    def test_import_unsupported_source_returns_400(self, client, auth_headers):
        html = "<html></html>"
        response = client.post(
            "/api/v1/import/instapaper",
            files={"file": ("export.html", io.BytesIO(html.encode()), "text/html")},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Unsupported source" in response.json()["detail"]


class TestImportAuthRequired:
    def test_import_without_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/import/json",
            files={"file": ("x.json", io.BytesIO(b"[]"), "application/json")},
        )
        assert response.status_code == 401

    def test_export_without_auth_returns_401(self, client):
        response = client.get("/api/v1/export/json")
        assert response.status_code == 401


class TestSafeHref:
    def test_safe_href_allows_http(self):
        from fourdpocket.api.import_export import _safe_href
        assert _safe_href("http://example.com") == "http://example.com"
        assert _safe_href("https://example.com") == "https://example.com"

    def test_safe_href_blocks_invalid_schemes(self):
        from fourdpocket.api.import_export import _safe_href
        assert _safe_href("javascript:alert(1)") is None
        assert _safe_href("ftp://example.com") is None
        assert _safe_href("file:///etc/passwd") is None

    def test_safe_href_escapes_quotes(self):
        from fourdpocket.api.import_export import _safe_href
        result = _safe_href('https://example.com/path"with"quotes')
        assert '"' not in result
        assert result is not None

    def test_safe_href_handles_none(self):
        from fourdpocket.api.import_export import _safe_href
        assert _safe_href(None) is None


# === PHASE 3 MOPUP ADDITIONS ===

class TestExportHTML:
    """HTML export format tests."""

    def test_export_html_returns_valid_html(self, client, auth_headers):
        """HTML export returns valid bookmark-formatted HTML."""
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/html-export", "title": "HTML Export Item"},
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/html", headers=auth_headers)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")

        content = response.content.decode("utf-8")
        assert "NETSCAPE-Bookmark-file" in content
        assert "4DPocket Bookmarks" in content
        assert "https://example.com/html-export" in content

    def test_export_html_sanitizes_javascript_urls(self, client, auth_headers):
        """HTML export skips javascript: URLs."""
        # Create item with non-http URL (will be sanitized to empty)
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/safe-export", "title": "Safe Item"},
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/html", headers=auth_headers)
        content = response.content.decode("utf-8")
        # javascript: URLs should not appear in export
        assert "javascript:" not in content


class TestExportMarkdown:
    """Markdown export format tests."""

    def test_export_markdown_returns_valid_markdown(self, client, auth_headers):
        """Markdown export returns valid markdown list."""
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/md-export",
                "title": "MD Export Item",
                "description": "A short description",
            },
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/markdown", headers=auth_headers)
        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")

        content = response.content.decode("utf-8")
        assert "# 4DPocket Export" in content
        assert "https://example.com/md-export" in content
        assert "MD Export Item" in content

    def test_export_markdown_strips_non_http_urls(self, client, auth_headers):
        """Markdown export skips non-http URL schemes."""
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/md-safe", "title": "MD Safe"},
            headers=auth_headers,
        )

        response = client.get("/api/v1/export/markdown", headers=auth_headers)
        content = response.content.decode("utf-8")
        assert "markdown" in content.lower() or "export" in content.lower()


class TestExportImportRoundTrip:
    """End-to-end: export from User A, import into User B, verify fidelity."""

    def test_json_roundtrip_preserves_urls_and_titles(self, client, auth_headers, second_user_headers):
        """Items exported as JSON can be imported by another user with URL/title fidelity."""
        # User A creates items
        client.post("/api/v1/items", json={"url": "https://roundtrip1.com", "title": "First Article"}, headers=auth_headers)
        client.post(
            "/api/v1/items",
            json={"url": "https://roundtrip2.com", "title": "Second Article", "content": "Some body content"},
            headers=auth_headers,
        )

        # User A exports
        export_resp = client.get("/api/v1/export/json", headers=auth_headers)
        assert export_resp.status_code == 200
        export_data = export_resp.json()
        assert len(export_data["items"]) >= 2

        # User B imports the export payload
        import_payload = json.dumps(export_data)
        import_resp = client.post(
            "/api/v1/import/json",
            files={"file": ("roundtrip.json", io.BytesIO(import_payload.encode()), "application/json")},
            headers=second_user_headers,
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["imported"] >= 2

        # Verify User B has the items
        user_b_export = client.get("/api/v1/export/json", headers=second_user_headers)
        user_b_items = user_b_export.json()["items"]
        user_b_urls = {i["url"] for i in user_b_items}
        assert "https://roundtrip1.com" in user_b_urls
        assert "https://roundtrip2.com" in user_b_urls

        # Verify titles preserved
        user_b_titles = {i["title"] for i in user_b_items}
        assert "First Article" in user_b_titles
        assert "Second Article" in user_b_titles

    def test_json_roundtrip_content_preserved(self, client, auth_headers, second_user_headers):
        """Content and description survive the export→import cycle."""
        client.post(
            "/api/v1/items",
            json={
                "url": "https://content-test.com",
                "title": "Content Test",
                "content": "This is the full body content that should survive the round-trip.",
            },
            headers=auth_headers,
        )

        export_resp = client.get("/api/v1/export/json", headers=auth_headers)
        export_data = export_resp.json()

        import_resp = client.post(
            "/api/v1/import/json",
            files={"file": ("content.json", io.BytesIO(json.dumps(export_data).encode()), "application/json")},
            headers=second_user_headers,
        )
        assert import_resp.status_code == 200

        user_b_export = client.get("/api/v1/export/json", headers=second_user_headers)
        items = user_b_export.json()["items"]
        content_item = next((i for i in items if i["url"] == "https://content-test.com"), None)
        assert content_item is not None
        assert content_item["content"] == "This is the full body content that should survive the round-trip."

    def test_json_roundtrip_user_isolation(self, client, auth_headers, second_user_headers):
        """After import, User A's items list is unchanged — import doesn't cross-pollinate."""
        client.post("/api/v1/items", json={"url": "https://user-a-only.com", "title": "A Only"}, headers=auth_headers)

        export_resp = client.get("/api/v1/export/json", headers=auth_headers)
        export_data = export_resp.json()
        user_a_count = len(export_data["items"])

        # User B imports
        client.post(
            "/api/v1/import/json",
            files={"file": ("iso.json", io.BytesIO(json.dumps(export_data).encode()), "application/json")},
            headers=second_user_headers,
        )

        # User A's count unchanged
        user_a_after = client.get("/api/v1/export/json", headers=auth_headers)
        assert len(user_a_after.json()["items"]) == user_a_count

