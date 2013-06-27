CREATE TRIGGER IF NOT EXISTS KTE_Activity_DismissNewBookTiles
AFTER INSERT ON Activity
FOR EACH ROW
WHEN (NEW.Type IN ('RecentBook') AND EXISTS (SELECT 1 FROM content c where c.contentId = NEW.Id and c.ReadStatus = 0))
BEGIN
    UPDATE Activity SET Enabled = 'false' WHERE rowid = new.rowid;
    UPDATE Activity SET Enabled = 'false' WHERE Type = 'Library';
END