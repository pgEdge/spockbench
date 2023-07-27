\set bid (random(1, :scale / :numnodes) - 1) * :numnodes + :nodeid
\set rmtbid random(1,:scale)
\set aid random(1, 100000) + 100000 * (:rmtbid - 1)
\set tid random(1, 10) + 10 * (:rmtbid - 1)
\set delta random(-5000, 5000)
BEGIN;
UPDATE pgbench_accounts SET abalance = abalance + :delta, filler = 'node ' || :nodeid || ' at ' || CURRENT_TIMESTAMP WHERE aid = :aid;
SELECT abalance FROM pgbench_accounts WHERE aid = :aid;
UPDATE pgbench_tellers SET tbalance = tbalance + :delta, filler = 'node ' || :nodeid || ' at ' || CURRENT_TIMESTAMP WHERE tid = :tid;
UPDATE pgbench_branches SET bbalance = bbalance + :delta WHERE bid = :bid;
INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) VALUES (:tid, :bid, :aid, :delta, CURRENT_TIMESTAMP);
END;
