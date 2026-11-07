"""The database behind the server: concurrent calls, the event loop, and paginated invoices."""

import time
from datetime import date, timedelta

import anyio
import pytest
from mcp import Client
from mcp.types import ResourceTemplateReference

from pachatraining_mcp import server
from pachatraining_mcp.server import connect

pytestmark = pytest.mark.anyio


async def test_simultaneous_calls(client: Client):
    """Eight calls at once, as a host may send them: each one needs a connection of its own."""
    results = []

    async def call():
        results.append(await client.call_tool("sessions_in_week", {"monday": "2026-11-16"}))

    async with anyio.create_task_group() as tg:
        for _ in range(8):
            tg.start_soon(call)
    assert [r.content[0].text for r in results if r.is_error] == []
    assert [r.structured_content["count"] for r in results] == [36] * 8


async def test_completion_leaves_the_server_free(client: Client, monkeypatch):
    """A slow query behind the completion handler must not hold the other requests."""
    real_codes = server.course_codes

    def slow_codes(prefix):
        time.sleep(1.0)  # what the driver does while SQL Server works: it blocks the thread
        return real_codes(prefix)

    monkeypatch.setattr(server, "course_codes", slow_codes)
    listed_at = []

    async def complete():
        await client.complete(
            ResourceTemplateReference(type="ref/resource", uri="pachatraining://course/{code}"),
            {"name": "code", "value": "LNX"},
        )

    async def list_tools():
        await anyio.sleep(0.2)
        await client.list_tools()
        listed_at.append(time.perf_counter() - start)

    # The in-memory client shares the server's event loop: a blocked loop delays its sleep
    # too, so the time is taken from one start for both requests.
    start = time.perf_counter()
    async with anyio.create_task_group() as tg:
        tg.start_soon(complete)
        tg.start_soon(list_tools)
    assert listed_at[0] < 0.6, f"tools/list answered after {listed_at[0]:.2f} s, behind it"


async def test_unpaid_first_page(client: Client):
    result = await client.call_tool("unpaid_invoices", {"as_of": "2026-11-16"})
    assert not result.is_error, result.content[0].text
    page = result.structured_content
    assert page["total"] == 4301
    assert len(page["invoices"]) == server.PAGE_SIZE == 50
    assert page["invoices"][0]["invoice_code"] == "FA2010-000018"
    assert page["invoices"][0]["due_date"] == "2010-12-03"
    assert page["next_cursor"]


async def test_unpaid_pages_cover_the_result(client: Client):
    """Following next_cursor gives every unpaid invoice once, in order, and then stops."""
    args = {"as_of": "2026-11-16", "days": 3650}
    seen, pages = [], 0
    while True:
        result = await client.call_tool("unpaid_invoices", args)
        assert not result.is_error, result.content[0].text
        page = result.structured_content
        assert len(page["invoices"]) <= 50
        seen += [(i["due_date"], i["invoice_code"]) for i in page["invoices"]]
        pages += 1
        if "next_cursor" not in page or page["next_cursor"] is None:
            break
        args["cursor"] = page["next_cursor"]
    cutoff = date(2026, 11, 16) - timedelta(days=3650)
    with connect() as cn:
        cur = cn.cursor()
        cur.execute("SELECT InvoiceCode FROM Mcp.UnpaidInvoice WHERE DueDate < ?", (cutoff,))
        expected = {r[0] for r in cur.fetchall()}
    assert [code for _, code in seen] == [code for _, code in sorted(seen)]  # ordered, no repeat
    assert len(seen) == len(set(seen)) == page["total"] == len(expected) == 1064
    assert {code for _, code in seen} == expected
    assert pages == 22


async def test_unpaid_refuses_a_bad_cursor(client: Client):
    result = await client.call_tool("unpaid_invoices", {"as_of": "2026-11-16", "cursor": "abc"})
    assert result.is_error
    assert "Invalid cursor" in result.content[0].text
    first = await client.call_tool("unpaid_invoices", {"as_of": "2026-11-16"})
    cursor = first.structured_content["next_cursor"]
    other = await client.call_tool("unpaid_invoices", {"as_of": "2026-11-17", "cursor": cursor})
    assert other.is_error
    assert "another as_of or days" in other.content[0].text
