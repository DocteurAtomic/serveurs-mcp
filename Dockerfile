# The image of the MCP server: Streamable HTTP on port 8000, as a user without rights.
#   docker build -t pachatraining-mcp .
# No secret goes in: .dockerignore keeps .env out of the build context, and the passwords and
# tokens reach the container as environment variables when it starts (compose.yaml).

# 1. Build: uv installs the locked dependencies, then the project, into /app/.venv.
FROM docker.io/library/python:3.13-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
# Compiled .pyc files make the first start faster; copies, not links, since the cache stays
# behind in this stage; and the Python of the image, never a downloaded one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# The dependencies first, in their own layer: it is rebuilt only when uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Then the project, installed as a package (--no-editable): the next stage needs no source.
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# 2. Run: the same Python, the environment of stage 1, no uv, no source, no compiler.
FROM docker.io/library/python:3.13-slim-trixie
# The ODBC driver that mssql-python ships needs three system libraries the slim image lacks
# (ldd on libmsodbcsql-18: libltdl.so.7, libkrb5.so.3, libgssapi_krb5.so.2). Without them,
# every tool fails with "Failed to load the driver".
RUN apt-get update \
 && apt-get install -y --no-install-recommends libltdl7 libkrb5-3 libgssapi-krb5-2 \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --no-create-home mcp
COPY --from=build /app/.venv /app/.venv
# In a container, 127.0.0.1 is the container itself: the server listens on every interface
# of its own network namespace, and compose.yaml publishes the port on the host's 127.0.0.1.
ENV PATH=/app/.venv/bin:$PATH \
    PACHA_HTTP_LISTEN=0.0.0.0 \
    PACHA_HTTP_PORT=8000
USER mcp
EXPOSE 8000
CMD ["pachatraining-mcp", "--http"]
