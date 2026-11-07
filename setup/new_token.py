"""Draws the token of one colleague, adds it to PACHA_TOKENS (or PACHA_READ_TOKENS) in .env, and
prints it once.

    uv run python setup/new_token.py alice              prints the token on stdout
    uv run python setup/new_token.py alice > alice.token
    uv run python setup/new_token.py --read carol       a token that reads only

The token goes to the colleague, who puts it in their environment as PACHA_TOKEN, never in a
file git sees. Drawing again for the same name replaces the old token: the old one is then
refused. The server reads .env when it starts, so restart it to take a new token into account.
"""

import re
import secrets
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"


def main() -> int:
    args = sys.argv[1:]
    variable = "PACHA_TOKENS"
    if args[:1] == ["--read"]:
        variable, args = "PACHA_READ_TOKENS", args[1:]
    if len(args) != 1 or not re.fullmatch(r"[a-z][a-z0-9._-]{0,31}", args[0]):
        print(f"usage: {sys.argv[0]} [--read] <name>  (lowercase letters, digits, . _ -)",
              file=sys.stderr)
        return 2
    name = args[0]
    if not ENV.exists():
        print(f"No {ENV}: run ./setup/install.sh first.", file=sys.stderr)
        return 1
    token = secrets.token_urlsafe(32)
    lines = ENV.read_text().splitlines()
    pairs, out = [], []
    for line in lines:
        if line.startswith(f"{variable}="):
            pairs = [p for p in line.split("=", 1)[1].split(",") if p.strip()]
            continue
        out.append(line)
    kept = [p for p in pairs if p.split(":", 1)[0].strip() != name]
    action = "replaced" if len(kept) < len(pairs) else "added"
    pairs = kept
    pairs.append(f"{name}:{token}")
    out.append(f"{variable}={','.join(pairs)}")
    ENV.write_text("\n".join(out) + "\n")
    print(token)
    print(f"Token of {name} {action} in {variable} (.env). Restart the server to use it.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
