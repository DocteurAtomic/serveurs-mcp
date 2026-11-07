"""Points the MCP server at one of the two accounts of the lab, in .env, and prints no password.

    uv run python setup/use_account.py mcp_reader    the restricted account (module 8 on)
    uv run python setup/use_account.py pacha_app     the account of modules 1 to 7

Sets PACHA_SQL_USER, and copies into PACHA_SQL_PASSWORD the password that install.sh wrote
for that account (MCP_READER_PASSWORD or PACHA_APP_PASSWORD). The other lines are kept.
"""

import sys
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"
ACCOUNTS = {"mcp_reader": "MCP_READER_PASSWORD", "pacha_app": "PACHA_APP_PASSWORD"}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ACCOUNTS:
        print(f"usage: {sys.argv[0]} {'|'.join(ACCOUNTS)}", file=sys.stderr)
        return 2
    user = sys.argv[1]
    lines = ENV.read_text().splitlines()
    values = dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    password = values.get(ACCOUNTS[user], "")
    if not password:
        print(f"{ACCOUNTS[user]} is empty in {ENV}: run ./setup/install.sh first.", file=sys.stderr)
        return 1
    out = []
    for line in lines:
        if line.startswith("PACHA_SQL_USER="):
            line = f"PACHA_SQL_USER={user}"
        elif line.startswith("PACHA_SQL_PASSWORD="):
            line = f"PACHA_SQL_PASSWORD={password}"
        out.append(line)
    ENV.write_text("\n".join(out) + "\n")
    print(f"The server now connects as {user} (.env updated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
