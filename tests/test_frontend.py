import asyncio

from app import main


def test_frontend_is_served_at_root():
    response = asyncio.run(main.frontend())

    assert response.path == main.INDEX_HTML
    assert main.INDEX_HTML.exists()
