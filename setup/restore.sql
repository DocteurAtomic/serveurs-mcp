-- Run by install.sh as sa. Creates master.dbo.restore_training, which restores the delivered
-- backup under a given name, then restores the reference database if it is missing.
USE master;
GO
CREATE OR ALTER PROCEDURE dbo.restore_training
    @db sysname = N'PachadataTraining'  -- another name restores a separate copy
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @data nvarchar(260) = N'/var/opt/mssql/data/' + @db + N'.mdf',
            @log nvarchar(260) = N'/var/opt/mssql/data/' + @db + N'_log.ldf',
            @q nvarchar(max), @n nvarchar(300) = QUOTENAME(@db);
    IF DB_ID(@db) IS NOT NULL
    BEGIN
        SET @q = N'ALTER DATABASE ' + @n + N' SET SINGLE_USER WITH ROLLBACK IMMEDIATE;';
        EXEC (@q);
    END;
    RESTORE DATABASE @db
        FROM DISK = N'/var/opt/mssql/backup/PachadataTraining-2026-10.bak'
        WITH REPLACE,
             MOVE N'PachadataTraining' TO @data,
             MOVE N'PachadataTraining_log' TO @log;
    -- The backup is at level 160 (built on SQL Server 2022); the lab runs at level 170,
    -- like the other SQL Server 2025 courses of Docteur Atomic.
    SET @q = N'ALTER DATABASE ' + @n + N' SET MULTI_USER; ALTER DATABASE ' + @n
           + N' SET COMPATIBILITY_LEVEL = 170;';
    EXEC (@q);
END;
GO
IF DB_ID(N'PachadataTraining') IS NULL
    EXEC dbo.restore_training;
ELSE
    PRINT 'PachadataTraining already exists: not restored.';
GO
