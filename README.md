# spockbench - A Python utility to test asynchronous multi-master replication

* [Overview](#overview)
* [What is wrong with pgbench](#what-is-wrong-with-pgbench)
* [Installation](#installation)
* [Running spockbench](#running-spockbench)
* [What spockbench does](#what-spockbench-does)
* [Checking consistency](#checking-consistency)
* [License](#license)

## Overview

`spockbench` is a Python utility to run `pgbench` in a way
that is more suitable for a distributed, asynchronous
multi-master replication cluster like pgEdge Spock.

The default `pgbench` workload is wrong and nowhere near of
resembling the TPC-B specification in several aspects. `spockbench`
tries to fix that while at the same time add some complexity
that is needed to test an asynchronous multi-master replication
system.

## What is wrong with pgbench?

TL;DR: a lot

`pgbench` does not use BID, TID and AID combinations that are
compliant with the TPC-B rules 5.3.3, 5.3.4 and 5.3.5. These rules
tie the BID to the TID (every teller belongs to only one branch)
and the AID to the BID in 85% of the transactions. Guess what, every
teller works in only one branch and every
customer (account) has a home branch where they do business 85%
of the time.

This may not be significant for a stand-alone system, but it is very
significant for a distributed system where data locality is affecting
the probability of update-update conflicts. In detail:

1)  pgbench does not use the correct BID

	The TPC-B specification rule 5.3.3 requires that the TID for the
	transaction must be chosen first. Rule 5.3.4 then dictates the BID because
	every teller's BID is `(TID - 1) / 10 + 1`.

2)  pgbench does not use the correct AID

	Like the BID, the TPC-B rule 5.3.5 requires that AID must be chosen
	from the accounts belonging
	to the branch of the teller (BID) in 85% of transactions. That
	means that the AID of the transaction should be within the 100,000
	accounts belonging to the branch.

`pgbench` ignores all of those rules and just plasters transactions
all over the place, using random numbers for BID, TID and AID without
any relationship.

The problem with this is that a distributed system has natural 
locality. People living in Boston will usually go to a branch in Boston.
So they will deal with a teller in Boston.
The TPC-B says that in 15% of cases the customer (ACCOUNT)
is remote. So in 15% of the transactions the TID and BID in the
ACCOUNTS table should not match. But only in 15%.

Applied to a distributed system, each branch would have a home database.
All transactions belonging to a BID would happen
on that home database. Which means that only 15% of ACCOUNTS
updates would create a possible update-update conflict for the
replication system. Given that there are 100,000 accounts per branch,
this isn't generating a tremendous rate of conflicts where two or more
nodes in the replication cluster simultaneously update an ACCOUNTS
row with the same AID.

In addition to all that, the transaction profile of the
TPC-B benchmark doesn't cover all problems an asynchronous multi-master
replication system has to deal with. The only columns ever updated
by the TPC-B transaction are the balances. Those are columns where
a last-update-wins conflict resolution fails and which will therefore be
configured so that Spock will use `delta-conflict-avoidance` (see below).
To test the correctness of last-update-wins the `spockbench` transaction
profiles also update the FILLER column with some generated string.

Finally the TPC-B's requirement that all tellers are strictly working
in their home branch is unrealistic. Back in the 80's when I was a
bank clerk we would routinely help out in another branch to cover
for vacation or called out sick tellers and clerks. So a teller working
in a remote branch is normal but infrequent.
Because it is an easy way to introduce a
large amount of update-update conflicts on a small number of rows,
`spockbench` has a transaction profile **remote-TA** that will use
a random TID not related to the current BID. It is not used by default
but can be activated with the **--spock-tx-mix=** option.


## Installation

`spockbench` is a pure Python3 utility installed via `distutils`. 
It is strongly recommended to create and activate a
[Python Virtual Environment](https://docs.python.org/3/library/venv.html)
and then run
```
cd spockbench
python ./setup.py install
```
This will build and install the `spockbench` package in the current
user's virtual environmen so that the tools `spockbench` and
`spockbench-check` become available in `$PATH`.

## Running spockbench

`spockbench` is a wrapper around `pgbench`. This section will
only cover the differences between `pgbench` and `spockbench`.
Being familiar with running
[pgbench](https://www.postgresql.org/docs/current/pgbench.html)
is assumed.

### pgbench options not available in spockbench

There are some `pgbench` options that are used internally by `spockbench`
or make no sense in its context and therefore are not available.
These are

* **-I, --init-steps=[dtgGvpf]**
* **-f, --file=FILENAME[@W]**
* **-b, --builtin=NAME[@W]**

The **--init-steps** option is used by `spockbench` to separate phases
during **--initialize** where schema modifications are needed in
between creating the schema, loading the initial data and finalizing
the schema.

The **--file** option is not available because `spockbench` uses that
to run its own custom transaction profiles, matching the modified
schema.

The **--builtin** option makes no sense for the same reason.

### spockbench specific new options

*	**--spock-num-nodes=N**

	Informs `spockbench` about how many nodes are in the
	replication cluster. It is passed to the transaction profiles
	as **:numnodes** variable and used in conjunction with the
	**--spock-node=N** option to specify data locality.

*	**--spock-node=N**

	Specfies the node ID of the database `spockbench` is connecting
	to. Together with the **--spock-num-nodes** and **--scale** options
	this defines which branches this `spockbench` instance is going
	to work on.
	
	In the custom transaction profiles the BID is generated as
	```
	\set bid (random(1, :scale / :numnodes) - 1) * :numnodes + :branch
	```
	where **:scale** is the number of BRANCHES, **:numnodes** is the
	number of Spock replication cluster nodes and **:branch** is
	the node ID specified via **--spock-node**. In a 3-node Spock
	cluster this will make node 1 work on branches 1, 4, 7, ...,
	node 2 work on branches 2, 5, 8, ... and node 3 work on branches
	3, 6, 9, ...
	
	For obvious reasons it is recommended to make
	**--scale** a multiple of **--spock-num-nodes**.

*	**--spock-tx-mix=LOCAL,REMOTE_A,REMOTE_TA**

	Specifies the probabilities for the three `spockbench` transaction
	profiles **local, remote-A and remote-TA. See below for details.

	The default is **--spock-tx-mix=775,225,0** which is equivalent
	to the TPC-B requirement of 15% of ACCOUNTS rows being accessed
	from a remote branch (a branch that does not have the local node
	has home database).

*	**--spock-no-hid**

	By default `spockbench` adds a primary key column HID to the
	pgbench_history table. This can be used for database comparison
	as well as allowing the HISTORY table to be added to replication
	without creating a separate insert-only set. the --spock-no-hid
	option suppresses this column.

*	**--spock-no-delta-apply**

	This option suppresses configuration of the balance columns
	to log old values for delta-conflict-avoidance (see below).

*   **--no-data**
*   **--data-only**

	These two options allow to separate schema creation from
	loading the initial data. This way one can create the
	schema with empty tables, setup replication including
	subscriptions and then load the initial data on only one
	node. Or create one node with data, other nodes without
	data and use the *sync_data* feature when subscribing them.

## What spockbench does

Instead of implementing a new benchmark driver from scratch
`spockbench` is a wrapper around `pgbench`, using the script-file
feature of `pgbench` with
multiple different scripts and a modified schema.

### Initializing the database schema

Initializing a `spockbench` database is almost identical to
using `pgbench`. The only difference is that
during `spockbench --initialize` the following additional SQL
is executed:
```
-- ----------------------------------------------------------------------
-- Configure all the balance columns for delta-conflict-avoidance.
-- ----------------------------------------------------------------------
ALTER TABLE pgbench_accounts ALTER COLUMN abalance SET (LOG_OLD_VALUE=true);
ALTER TABLE pgbench_branches ALTER COLUMN bbalance SET (LOG_OLD_VALUE=true);
ALTER TABLE pgbench_tellers ALTER COLUMN tbalance SET (LOG_OLD_VALUE=true);
```

This can be suppressed with the **--spock-no-delta-apply** option.
Using this together with the **--spock-tx-mix** option to run a load
with a high rate of conflict on a multi-master cluster will make the
[checks](check-consistency) fail.

These ALTER TABLE commands cause Spock to treat the columns via
delta-conflict-avoidance. That means that they will not follow
the default *last-update-wins* pattern, but that all updates are
applied by adding the delta of what happened on the remote. So

**new-value = current-value + (remote-new - remote-old)**

This is pretty much the definition of a CRDT. Only that Spock is
doing it on standard builtin data types like INT, BIGINT and NUMERIC
by flagging the column with the above ALTER TABLE statements.

### Performing a benchmark

Since `spockbench` is designed to run against multiple nodes of an
asynchonous multi-master replication cluster, there are additional
command line options to use. These options inform `spockbench` how
many nodes there are and what the desired transaction mix is with
respect to update-update conflicts.

The first thing to do is to initialize the database, load the data
and set up the replication. Setting up replication will not be
covered here as that is clearly beyond the scope of this README.

Let us create a `spockbench` database:
```
(venv) [postgres@db1 spockbench]$ createdb spockdb
(venv) [postgres@db1 spockbench]$ spockbench -i -s12 -F75 --spock-node=1 spockdb
dropping old tables...
NOTICE:  table "pgbench_accounts" does not exist, skipping
NOTICE:  table "pgbench_branches" does not exist, skipping
NOTICE:  table "pgbench_history" does not exist, skipping
NOTICE:  table "pgbench_tellers" does not exist, skipping
creating tables...
generating data (client-side)...
1200000 of 1200000 tuples (100%) done (elapsed 1.85 s, remaining 0.00 s)
creating primary keys...
done in 3.29 s (drop tables 0.11 s, create tables 0.07 s, client-side generate 2.63 s, primary keys 0.49 s).
configuring balance columns for delta-conflict-avoidance
adding primary key hid to pgbench_history
```
That command more or less ran a default `pgbench -i -s12` but also
configured BBALANCE, TBALANCE and ABALANCE for delta-conflict-avoidance
and added an HID primary key to the HISTORY table. It is important to use
different node-IDs (--spock-node) values for each node to make this
primary key conflict free. `spockbench` configures the underlying
sequence to start on the node-ID and increment by 100.

Now on to running a benchmark:
```
(venv) [postgres@db1 spockbench]$ spockbench -s12 -c20 -T60 -P5 spockdb
```
will do *almost* the exact same thing as `pgbench` would do.

```
(venv) [postgres@db1 spockbench]$ spockbench -n -s12 -c10 -T60 -P5 --spock-node=1 --spock-num-nodes=3 spockdb
pgbench (15.3)
progress: 5.0 s, 42.8 tps, lat 57.185 ms stddev 12.868, 0 failed
progress: 10.0 s, 159.4 tps, lat 68.811 ms stddev 97.210, 0 failed
progress: 15.0 s, 171.4 tps, lat 58.201 ms stddev 14.970, 0 failed
progress: 20.0 s, 165.0 tps, lat 60.637 ms stddev 19.750, 0 failed
progress: 25.0 s, 171.2 tps, lat 58.354 ms stddev 13.634, 0 failed
progress: 30.0 s, 165.8 tps, lat 60.244 ms stddev 18.195, 0 failed
progress: 35.0 s, 172.6 tps, lat 57.978 ms stddev 15.549, 0 failed
progress: 40.0 s, 170.6 tps, lat 58.573 ms stddev 14.411, 0 failed
progress: 45.0 s, 172.6 tps, lat 57.943 ms stddev 15.652, 0 failed
progress: 50.0 s, 169.6 tps, lat 59.040 ms stddev 14.701, 0 failed
progress: 55.0 s, 166.8 tps, lat 59.727 ms stddev 20.286, 0 failed
progress: 60.0 s, 174.2 tps, lat 57.485 ms stddev 13.777, 0 failed
transaction type: multiple scripts
scaling factor: 1
query mode: simple
number of clients: 10
number of threads: 1
maximum number of tries: 1
duration: 60 s
number of transactions actually processed: 9520
number of failed transactions: 0 (0.000%)
latency average = 59.601 ms
latency stddev = 32.226 ms
initial connection time = 3264.247 ms
tps = 167.643528 (without initial connection time)
SQL script 1: /tmp/spockbench-local.sql.317621
 - weight: 775 (targets 77.5% of total)
 - 7410 transactions (77.8% of total, tps = 130.487242)
 - number of failed transactions: 0 (0.000%)
 - latency average = 59.671 ms
 - latency stddev = 32.588 ms
SQL script 2: /tmp/spockbench-remote-A.sql.317621
 - weight: 225 (targets 22.5% of total)
 - 2110 transactions (22.2% of total, tps = 37.156286)
 - number of failed transactions: 0 (0.000%)
 - latency average = 59.353 ms
 - latency stddev = 30.920 ms
SQL script 3: /tmp/spockbench-remote-TA.sql.317621
 - weight: 0 (targets 0.0% of total)
 - 0 transactions (0.0% of total, tps = 0.000000)
 - number of failed transactions: 0 (NaN%)
```
OK, first of all it ran 2 scripts (the third had a 0 probability so
it never fired). But other than that, it looks like it did what
`pgbench` would do.

However, that isn't really what happened. When we look at the
database this `spockbench` run only used branches 1, 4, 7 and 10:
```
spockdb=# select bid, count(bid) from pgbench_history group by 1 order by 1;
 bid | count
-----+-------
   1 |  2443
   4 |  2399
   7 |  2372
  10 |  2306
(4 rows)
```

### Running a distributed system

As pointed out earlier in a distributed system each branch has a home
database. What we see in the above example are the default values for
`spockbench` parameters

```
--spock-node=1 --spock-num-nodes=3
```

When we want to distribute the system over multiple nodes with a
reasonable level of concurrency over ACCOUNTS, we need to use those
parameters to control which branches have their home location on a
given node. For example, if we created a 4-node cluster with a total
of 12 branches, we would run the following command on node 2:
```
(venv) [postgres@db1 spockbench]$ spockbench -n -s12 -c10 -T60 -P5 --spock-node=2 --spock-num-nodes=4 spockdb
```
This would then create a BID distribution on node 2 looking like this:
```
spockdb=# select bid, count(bid) from pgbench_history group by 1 order by 1;
 bid | count
-----+-------
   2 |  2768
   6 |  2736
  10 |  2830
(3 rows)
```

While the BRANCHES and TELLERS tables have been kept 100% conflict
free, the ACCOUNTS table did receive some potential update-update
conflicts. 
```
spockdb=# select A.bid, count(A.bid) from pgbench_history H join pgbench_accounts A on A.aid = H.aid group by 1 order by 1;
 bid | count
-----+-------
   1 |   160
   2 |  2304
   3 |   146
   4 |   141
   5 |   161
   6 |  2277
   7 |   172
   8 |   160
   9 |   167
  10 |  2341
  11 |   154
  12 |   151
(12 rows)
```
As per the TPC-B specification, 15% of the transactions used an AID
that does not belong to the BID of the transaction. In the simulated
4-node cluster, each other node would also generate 85% of transactions
belonging to its home branches, as well as 15% of remote ones. This
does sound like a lot, but since there are 100,000 ACCOUNTS rows per
branch, the probability of actually creating an update-update conflict
is reather low.

### Controlling the conflict probability

The original TPC-B requires 15% of ACCOUNTS.BID to be different
than the BRANCHES.BID and TELLERS.BID of the transaction. 
`spockbench` accomplishes that by implementing separate transaction
profiles and running them with different weights.

*	**spockbench-local.sql**

	This transaction profile is picking the BID from the home branches
	of the node (controlled by --spock-node=N). It then generates a TID
	and AID that belong to that BID. This is a 100% local transaction.

*	**spockbench-remote-A.sql**

	This transaction profile is picking the BID from the home branches
	of the node. It then generates a TID that belongs to that BID and
	a completely random AID over the entire available range. This
	profile is used to create the remote AID part of the TPC-B
	specification.

*	**spockbench-remote-TA.sql**

	This is a transaction profile that is outside of the TPC-B
	specification. As mentioned above, tellers in the real world do
	sometimes work at a remote branch to cover for vacation, sick leave
	or other personel shortages. Simulating this however serves a different
	purpose than making the TPC-B more realistic. The TELLERS table is
	very small, compared to the ACCOUNTS table. Introducing any possible
	update-update conflict on this table will create a tremendous stress
	test on the last-update-wins logic of the replication system.

The mix of the three transaction profiles is controlled with the
option `--spock-tx-mix=L,RA,RTA` where L, RA and RTA are the
@W probability values given to the --file=FILENAME@W option.

The default transaction mix is
```
--spock-tx-mix=775,225,0
```
which are the correct numbers to produce a 15% remote AID mix on a
3-node cluster. The reason why it is NOT 850,150,0 is because the
**spockbench-remote-A.sql** transaction profile is selecting AID
uniformly from all accounts, including the home branches of the node.
The TPC-B specification asks for 15% to be remote, not including home branches.
So on a 3-node cluster we need to adjust for that by using a probability
of 15% / 2 * 3 = 22.5 and thus end up with @775, @225 and @0.

## Checking Consistency

A TPC-B database has inherent consistency requirements. After a
benchmark run the balance columns of the BRANCHES, TELLERS and
ACCOUNTS tables need to be equal to the sum of the corresponding
HISTORY rows. The file `spockbench-check.sql` verifies this and
can be executed with the command
```
spockbench-check [CONNECT-OPTIONS] [DATABASE-NAME]
```

The output should look like this:
```
 check | count |          description
-------+-------+--------------------------------
 OK    |     0 | bbalance <> history.sum(delta)
(1 row)

 check | count |          description
-------+-------+--------------------------------
 OK    |     0 | tbalance <> history.sum(delta)
(1 row)

 check | count |          description
-------+-------+--------------------------------
 OK    |     0 | abalance <> history.sum(delta)
(1 row)
```

## License

`spockbench` is licensed under the
[pgEdge Community License v1.0](PGEDGE-COMMUNITY-LICENSE.md)
