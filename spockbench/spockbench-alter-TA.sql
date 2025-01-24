-- ----------------------------------------------------------------------
-- Configure all the balance columns for delta-conflict-avoidance.
-- ----------------------------------------------------------------------
ALTER TABLE pgbench_accounts ALTER COLUMN abalance SET (LOG_OLD_VALUE=true, DELTA_APPLY_FUNCTION=spock.delta_apply);
ALTER TABLE pgbench_branches ALTER COLUMN bbalance SET (LOG_OLD_VALUE=true, DELTA_APPLY_FUNCTION=spock.delta_apply);
ALTER TABLE pgbench_tellers ALTER COLUMN tbalance SET (LOG_OLD_VALUE=true, DELTA_APPLY_FUNCTION=spock.delta_apply);

