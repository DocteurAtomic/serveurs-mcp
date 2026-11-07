-- Run by install.sh and reset-copy.sh as sa, once per database: the reference database and
-- each module copy. The database name comes from the environment variable DB, which sqlcmd
-- reads as a scripting variable. Safe to run again.
--
-- What it creates:
--   users pacha_app (db_datareader, EXECUTE on the Mcp procedures: modules 1 to 7)
--   and mcp_reader (SELECT on the Mcp schema, EXECUTE on its two procedures: module 8 on);
--   the Mcp schema: one view per read made by a tool or a resource of modules 1 to 7, and the
--   two procedures that are the only way the server writes. A person appears in a view by
--   display name only, never by email, phone or birth date.
USE [$(DB)];
GO
IF USER_ID(N'pacha_app') IS NULL CREATE USER pacha_app FOR LOGIN pacha_app;
IF USER_ID(N'mcp_reader') IS NULL CREATE USER mcp_reader FOR LOGIN mcp_reader;
ALTER ROLE db_datareader ADD MEMBER pacha_app;
IF SCHEMA_ID(N'Mcp') IS NULL EXEC (N'CREATE SCHEMA Mcp AUTHORIZATION dbo;');
GO

-- sessions_in_week, prompt review_week (module 1)
CREATE OR ALTER VIEW Mcp.SessionSummary AS
SELECT s.SessionId, s.StartDate, s.Duration, c.Code AS CourseCode, cl.Title AS CourseTitle,
       RTRIM(s.StatusCode) AS StatusCode, s.LanguageCode
FROM Course.Session AS s
JOIN Course.Course AS c ON c.CourseId = s.CourseId
LEFT JOIN Course.CourseLanguage AS cl ON cl.CourseId = s.CourseId AND cl.LanguageCode = 'EN';
GO

-- session_detail (exercise of module 1), Remarks for module 9
CREATE OR ALTER VIEW Mcp.SessionDetail AS
SELECT s.SessionId, s.StartDate, s.Duration, c.Code AS CourseCode, cl.Title AS CourseTitle,
       RTRIM(s.StatusCode) AS StatusCode, s.LanguageCode, c.MaxAttendees,
       (SELECT COUNT(*) FROM Enrollment.Enrollment AS e
        WHERE e.SessionId = s.SessionId AND e.CancellationDate IS NULL) AS EnrolledCount,
       s.TrainerId, CONCAT(tc.FirstName, ' ', tc.LastName) AS TrainerName,
       s.Remarks
FROM Course.Session AS s
JOIN Course.Course AS c ON c.CourseId = s.CourseId
LEFT JOIN Course.CourseLanguage AS cl ON cl.CourseId = s.CourseId AND cl.LanguageCode = 'EN'
LEFT JOIN Trainer.Trainer AS t ON t.TrainerId = s.TrainerId
LEFT JOIN Contact.Contact AS tc ON tc.ContactId = t.ContactId;
GO

-- resource pachatraining://session-statuses (module 5)
CREATE OR ALTER VIEW Mcp.SessionStatus AS
SELECT RTRIM(StatusCode) AS StatusCode, Label FROM Course.SessionStatus;
GO

-- resource template pachatraining://course/{code} and its completion (module 5)
CREATE OR ALTER VIEW Mcp.CourseSheet AS
SELECT c.Code AS CourseCode, cl.LanguageCode, cl.Title, cl.Subtitle, cl.Summary,
       cl.Prerequisites, cl.TargetAudience, cl.Objectives, c.Duration, c.MaxAttendees,
       c.CancellationDate
FROM Course.Course AS c
JOIN Course.CourseLanguage AS cl ON cl.CourseId = c.CourseId;
GO

-- unpaid_invoices (module 6). One row per invoice (not credit note) with an amount still due.
-- Payments are summed whatever their date: the data stops on 18 October 2026, before the
-- as_of date of the course.
CREATE OR ALTER VIEW Mcp.UnpaidInvoice AS
SELECT i.InvoiceCode, i.InvoiceDate, i.DueDate,
       COALESCE(co.Name, CONCAT(ct.FirstName, ' ', ct.LastName)) AS ClientName,
       i.GrossAmount, ISNULL(p.Paid, 0) AS PaidAmount, i.GrossAmount - ISNULL(p.Paid, 0) AS AmountDue,
       p.LastPaymentDate
FROM Enrollment.Invoice AS i
LEFT JOIN (SELECT InvoiceCode, SUM(Amount) AS Paid, MAX(PaymentDate) AS LastPaymentDate
           FROM Enrollment.Payment GROUP BY InvoiceCode) AS p ON p.InvoiceCode = i.InvoiceCode
LEFT JOIN Contact.Company AS co ON co.CompanyId = i.CompanyId
LEFT JOIN Contact.Contact AS ct ON ct.ContactId = i.ContactId
WHERE i.DocumentType = 'I' AND i.GrossAmount > ISNULL(p.Paid, 0);
GO

-- sessions_to_watch (exercise of module 6)
CREATE OR ALTER VIEW Mcp.SessionFill AS
SELECT s.SessionId, s.StartDate, c.Code AS CourseCode, RTRIM(s.StatusCode) AS StatusCode,
       c.MaxAttendees, f.EnrolledCount,
       CAST(f.EnrolledCount * 1.0 / NULLIF(c.MaxAttendees, 0) AS decimal(5, 2)) AS FillRate
FROM Course.Session AS s
JOIN Course.Course AS c ON c.CourseId = s.CourseId
CROSS APPLY (SELECT COUNT(*) AS EnrolledCount FROM Enrollment.Enrollment AS e
             WHERE e.SessionId = s.SessionId AND e.CancellationDate IS NULL) AS f;
GO

-- the confirmation of cancel_enrollment (exercise of module 7)
CREATE OR ALTER VIEW Mcp.EnrollmentSummary AS
SELECT e.EnrollmentId, e.SessionId, s.StartDate AS SessionStartDate, c.Code AS CourseCode,
       RTRIM(s.StatusCode) AS SessionStatus, CONCAT(ct.FirstName, ' ', ct.LastName) AS TraineeName,
       e.CancellationDate
FROM Enrollment.Enrollment AS e
JOIN Course.Session AS s ON s.SessionId = e.SessionId
JOIN Course.Course AS c ON c.CourseId = s.CourseId
LEFT JOIN Contact.Contact AS ct ON ct.ContactId = e.ContactId;
GO

-- trainer_load and the resource template pachatraining://trainer/{trainer_id}/month/{month}
-- (exercise of module 8). One row per trainer and month with engagements, the month as
-- YYYY-MM; a trainer without any engagement has one row whose Month is NULL, so that the
-- server tells an idle trainer from an unknown one.
CREATE OR ALTER VIEW Mcp.TrainerMonth AS
SELECT t.TrainerId, m.Month, ISNULL(m.SessionCount, 0) AS SessionCount,
       ISNULL(m.DayCount, 0) AS DayCount
FROM Trainer.Trainer AS t
OUTER APPLY (SELECT CONVERT(char(7), s.StartDate, 126) AS Month, COUNT(*) AS SessionCount,
                    SUM(e.DayCount) AS DayCount
             FROM Trainer.Engagement AS e
             JOIN Course.Session AS s ON s.SessionId = e.SessionId
             WHERE e.TrainerId = t.TrainerId
             GROUP BY CONVERT(char(7), s.StartDate, 126)) AS m;
GO

-- Where Mcp.CancelEnrollment keeps the reason: Enrollment.Enrollment has no column for it.
IF OBJECT_ID(N'Mcp.EnrollmentCancellation', N'U') IS NULL
    CREATE TABLE Mcp.EnrollmentCancellation (
        EnrollmentId int NOT NULL PRIMARY KEY,
        CancelledOn date NOT NULL,
        Reason varchar(200) NOT NULL);
GO

-- postpone_session (module 7). Reads no clock: @AsOf is the reference date of the caller.
CREATE OR ALTER PROCEDURE Mcp.PostponeSession
    @SessionId int, @NewStartDate date, @AsOf date
AS
BEGIN
    SET NOCOUNT, XACT_ABORT ON;
    DECLARE @status varchar(10), @start date, @msg nvarchar(200);
    BEGIN TRANSACTION;
    SELECT @status = RTRIM(StatusCode), @start = StartDate
    FROM Course.Session WITH (UPDLOCK, HOLDLOCK) WHERE SessionId = @SessionId;
    IF @start IS NULL
        SET @msg = CONCAT(N'Session ', @SessionId, N' does not exist.');
    ELSE IF @status NOT IN ('PLANNED', 'OPEN', 'CONFIRMED')
        SET @msg = CONCAT(N'Session ', @SessionId, N' is ', @status, N' and cannot be postponed.');
    ELSE IF @start < @AsOf
        SET @msg = CONCAT(N'Session ', @SessionId, N' started on ', @start, N', before ', @AsOf, N'.');
    ELSE IF @NewStartDate < @AsOf
        SET @msg = CONCAT(N'The new date ', @NewStartDate, N' is before ', @AsOf, N'.');
    ELSE IF @NewStartDate = @start
        SET @msg = CONCAT(N'Session ', @SessionId, N' already starts on ', @start, N'.');
    IF @msg IS NOT NULL
    BEGIN
        ROLLBACK;
        THROW 50001, @msg, 1;
    END;
    UPDATE Course.Session SET StartDate = @NewStartDate WHERE SessionId = @SessionId;
    COMMIT;
    SELECT @SessionId AS SessionId, @start AS OldStartDate, @NewStartDate AS NewStartDate;
END;
GO

-- cancel_enrollment (exercise of module 7). @AsOf becomes the cancellation date.
CREATE OR ALTER PROCEDURE Mcp.CancelEnrollment
    @EnrollmentId int, @Reason varchar(200), @AsOf date
AS
BEGIN
    SET NOCOUNT, XACT_ABORT ON;
    DECLARE @cancelled date, @found bit = 0, @status varchar(10), @msg nvarchar(200);
    BEGIN TRANSACTION;
    SELECT @found = 1, @cancelled = e.CancellationDate, @status = RTRIM(s.StatusCode)
    FROM Enrollment.Enrollment AS e WITH (UPDLOCK, HOLDLOCK)
    JOIN Course.Session AS s ON s.SessionId = e.SessionId
    WHERE e.EnrollmentId = @EnrollmentId;
    IF @found = 0
        SET @msg = CONCAT(N'Enrollment ', @EnrollmentId, N' does not exist.');
    ELSE IF @cancelled IS NOT NULL
        SET @msg = CONCAT(N'Enrollment ', @EnrollmentId, N' was already cancelled on ', @cancelled, N'.');
    ELSE IF @status IN ('COMPLETED', 'CANCELED')
        SET @msg = CONCAT(N'Enrollment ', @EnrollmentId, N' belongs to a session that is ', @status, N'.');
    ELSE IF NULLIF(LTRIM(@Reason), '') IS NULL
        SET @msg = N'A reason is required.';
    IF @msg IS NOT NULL
    BEGIN
        ROLLBACK;
        THROW 50002, @msg, 1;
    END;
    UPDATE Enrollment.Enrollment SET CancellationDate = @AsOf WHERE EnrollmentId = @EnrollmentId;
    INSERT Mcp.EnrollmentCancellation (EnrollmentId, CancelledOn, Reason)
    VALUES (@EnrollmentId, @AsOf, @Reason);
    COMMIT;
    SELECT @EnrollmentId AS EnrollmentId, @AsOf AS CancellationDate;
END;
GO

GRANT EXECUTE ON SCHEMA::Mcp TO pacha_app;
GRANT SELECT ON SCHEMA::Mcp TO mcp_reader;
GRANT EXECUTE ON OBJECT::Mcp.PostponeSession TO mcp_reader;
GRANT EXECUTE ON OBJECT::Mcp.CancelEnrollment TO mcp_reader;
GO
