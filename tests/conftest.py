"""What every test of the suite shares: the anyio backend, the lab, an in-memory client."""

import pytest
from mcp import Client

from pachatraining_mcp.server import connect, mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def lab():
    """Stop the whole run when SQL Server does not answer, and say so.

    Without the lab, every tool call is an error result and each test fails on its own
    assertion, which does not tell why. A skip would be worse: pytest exits 0 and the CI
    turns green on a suite that tested nothing.
    """
    try:
        with connect() as cn:
            cn.cursor().execute("SELECT 1")
    except Exception as exc:
        pytest.exit(f"The lab does not answer ({type(exc).__name__}: {exc}). "
                    "Start it with ./setup/install.sh.", returncode=3)


@pytest.fixture
async def client():
    """A fresh in-memory connection to the server for each test: no subprocess, no port."""
    async with Client(mcp, raise_exceptions=True) as c:
        yield c
