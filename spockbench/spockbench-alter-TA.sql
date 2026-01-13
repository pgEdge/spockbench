-- ----------------------------------------------------------------------
-- Configure all the balance columns for delta-conflict-avoidance.
-- ----------------------------------------------------------------------

ALTER TABLE pgbench_accounts ALTER COLUMN abalance SET NOT NULL;
ALTER TABLE pgbench_branches ALTER COLUMN bbalance SET NOT NULL;
ALTER TABLE pgbench_tellers ALTER COLUMN tbalance SET NOT NULL;
SELECT spock.delta_apply('pgbench_accounts', 'abalance', false);
SELECT spock.delta_apply('pgbench_branches', 'bbalance', false);
SELECT spock.delta_apply('pgbench_tellers', 'tbalance', false);
