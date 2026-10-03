import httpx
import pytest

from backend.app.main import app


@pytest.mark.anyio
async def test_frontend_and_styleguide_are_served() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        home = await client.get("/")
        guide = await client.get("/styleguide.html")
        module = await client.get("/js/main.js")
        styles = await client.get("/css/tokens.css")
        leaf_module = await client.get("/js/components/leaf-explode.js")
        leaf_styles = await client.get("/css/leaf-explode.css")
        leaf_poster = await client.get("/assets/leaf-sequence/webp/frame-001.webp")
    assert (
        home.status_code
        == guide.status_code
        == module.status_code
        == styles.status_code
        == leaf_module.status_code
        == leaf_styles.status_code
        == leaf_poster.status_code
        == 200
    )
    assert "Fieldnote" in home.text
    assert "Design system" in guide.text
    assert "HashRouter" in module.text
    assert "--forest: #1b4332" in styles.text
