-- Run by install.sh as sa. Creates (or resets the password of) the two logins of the course.
-- The passwords come from .env through the environment: sqlcmd reads PACHA_APP_PASSWORD and
-- MCP_READER_PASSWORD as scripting variables, so they never appear in this file.
--   pacha_app   the account "the team gave you", used by the server in modules 1 to 7
--   mcp_reader  the restricted account the server moves to in module 8
USE master;
GO
IF SUSER_ID(N'pacha_app') IS NULL
    CREATE LOGIN pacha_app WITH PASSWORD = N'$(PACHA_APP_PASSWORD)',
        DEFAULT_DATABASE = PachadataTraining, CHECK_EXPIRATION = OFF;
ELSE
    ALTER LOGIN pacha_app WITH PASSWORD = N'$(PACHA_APP_PASSWORD)';
GO
IF SUSER_ID(N'mcp_reader') IS NULL
    CREATE LOGIN mcp_reader WITH PASSWORD = N'$(MCP_READER_PASSWORD)',
        DEFAULT_DATABASE = PachadataTraining, CHECK_EXPIRATION = OFF;
ELSE
    ALTER LOGIN mcp_reader WITH PASSWORD = N'$(MCP_READER_PASSWORD)';
GO
