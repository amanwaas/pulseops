-- ============================================================================
-- PulseOps: 30-Day Retention Pruning Script for Neon PostgreSQL
-- ============================================================================
-- Purpose:
-- Neon free-tier databases provide 0.5 GiB of storage. High-frequency health
-- checks (e.g. 20 projects * 4 environments = 80 targets pinged every 60s)
-- generate ~115,200 rows/day (~10-15 MB/day).
--
-- Pruning records older than 30 days keeps table size bounded to ~3.5M rows
-- (~350MB index + data), safely inside the Neon free tier limit.
--
-- Method 1: Backend service background task (Runs automatically every 24 hours).
-- Method 2: Scheduled via pg_cron (if extension enabled on Neon):
--   SELECT cron.schedule('daily-health-log-cleanup', '0 3 * * *', $$
--     DELETE FROM health_logs WHERE checked_at < NOW() - INTERVAL '30 days';
--     VACUUM ANALYZE health_logs;
--   $$);
-- Method 3: Standalone SQL execution:
-- ============================================================================

DO $$
DECLARE
    deleted_count BIGINT;
    cutoff_time TIMESTAMPTZ := NOW() - INTERVAL '30 days';
BEGIN
    RAISE NOTICE 'Starting PulseOps health_logs retention cleanup prior to: %', cutoff_time;

    -- Delete in batches if table is very large to prevent table lock contention
    WITH deleted AS (
        DELETE FROM health_logs
        WHERE checked_at < cutoff_time
        RETURNING id
    )
    SELECT count(*) INTO deleted_count FROM deleted;

    RAISE NOTICE 'Retention cleanup completed. Successfully pruned % expired health logs.', deleted_count;
END $$;
