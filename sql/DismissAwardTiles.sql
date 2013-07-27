CREATE TRIGGER IF NOT EXISTS KTE_Activity_DismissAwardTiles
AFTER INSERT ON Activity
BEGIN
    UPDATE Activity SET Enabled = 'false' WHERE Type = 'Award';
END
