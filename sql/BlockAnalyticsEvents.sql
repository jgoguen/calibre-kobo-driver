DELETE FROM AnalyticsEvents;
CREATE TRIGGER IF NOT EXISTS KTE_BlockAnalyticsEvents
AFTER INSERT ON AnalyticsEvents
BEGIN
    DELETE FROM AnalyticsEvents;
END