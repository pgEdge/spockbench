#!/usr/bin/env python

####################################################################
######          Copyright (c)  2023-2025 PGEDGE           ##########
####################################################################

from getopt import getopt
import importlib.resources
import os
import subprocess
import sys

__all__ = ['SpockBench']

class SpockBench:
    def __init__(self):
        self.cmd = None
        self.is_init = False
        self.scale = None
        self.have_fkeys = False
        self.node = 1
        self.num_nodes = 3
        self.no_hid = False
        self.no_delta_apply = False
        self.no_data = False
        self.data_only = False
        self.tempfiles = []

        # ----
        # Copy the SQL scripts used by pgbench to /tmp
        # ----
        try:
            self.load_sql_scripts()
        except Exception as ex:
            self.cleanup()
            raise ex

    def run(self, *argv):
        self.parse_options(argv)

        # ----
        # The --scale option is required for creating the schema and
        # running the benchmark because :scale is not provided by
        # pgbench when running custom scripts.
        # ----
        if self.scale is None and self.no_data == False:
            print("spockbench requires the -s/--scale option",
                  file = sys.stderr)
            sys.exit(2)

        if self.is_init:
            self.run_init()
        else:
            self.run_benchmark()

    def check(self, *argv):
        # ----
        # Run the check script
        # ----
        self.parse_options(argv)

        cmd = ['psql']
        cmd.append('-q')
        cmd += ['-f', self.sql_fname['check']]
        cmd += self.pgbench_opts
        cmd += self.pgbench_args
        subprocess.run(cmd)

    def run_benchmark(self):
        # ----
        # Run pgbench
        # ----
        cmd = ['pgbench']
        cmd += ['-D', 'nodeid=' + str(self.node)]
        cmd += ['-D', 'scale=' + str(self.scale)]
        cmd += ['-D', 'numnodes=' + str(self.num_nodes)]
        cmd += ['-f', self.sql_fname['local'] + '@' + self.tx_local]
        cmd += ['-f', self.sql_fname['remote-A'] + '@' + self.tx_remote_A]
        cmd += ['-f', self.sql_fname['remote-TA'] + '@' + self.tx_remote_TA]
        cmd += self.pgbench_opts
        cmd += self.pgbench_args
        subprocess.run(cmd)

    def run_init(self):
        if self.data_only:
            # ----
            # Create the pgbench schema and load the data
            # ----
            cmd = ['pgbench']
            cmd.append('-i')
            cmd.append('-s')
            cmd.append(str(self.scale))
            cmd.append('-I')
            cmd.append('g')
            cmd += self.pgbench_iopts
            cmd += self.pgbench_args
            subprocess.run(cmd)
            return

        # ----
        # Create the pgbench schema and load the data
        # ----
        cmd = ['pgbench']
        cmd.append('-n')
        cmd.append('-i')
        if self.no_data:
            cmd.append('-I')
            if self.have_fkeys:
                cmd.append('dtpfv')
            else:
                cmd.append('dtpv')
        else:
            cmd.append('-s')
            cmd.append(str(self.scale))
        cmd += self.pgbench_iopts
        cmd += self.pgbench_args
        subprocess.run(cmd)

        # ----
        # Configure balance columns for delta-conflict-avoidance
        # ----
        if self.no_delta_apply == False:
            cmd = ['pgbench']
            cmd.append('-n')
            cmd.append('-c1')
            cmd.append('-t1')
            cmd += ['-f', self.sql_fname['alter-TA']]
            cmd += self.pgbench_opts
            cmd += self.pgbench_args
            print("configuring balance columns for delta-conflict-avoidance")
            subprocess.run(cmd, stdout = subprocess.DEVNULL)

        # ----
        # Add column pgbench_history.hid as a primary key for replication
        # systems that cannot replicate tables without a PK.
        # ----
        if self.no_hid == False:
            cmd = ['pgbench']
            cmd.append('-n')
            cmd.append('-c1')
            cmd.append('-t1')
            cmd += ['-f', self.sql_fname['alter-H']]
            cmd += ['-D', 'nodeid=' + str(self.node)]
            cmd += self.pgbench_opts
            cmd += self.pgbench_args
            print("adding primary key hid to pgbench_history")
            subprocess.run(cmd, stdout = subprocess.DEVNULL)

    def parse_options(self, argv):
        self.pgbench_opts = []
        self.pgbench_iopts = []
        self.tx_local = '775'
        self.tx_remote_A = '225'
        self.tx_remote_TA = '0'

        try:
            opts, self.pgbench_args = getopt(argv,
                "iF:s:c:Cj:lL:M:nP:rR:t:T:dh:p:U:",
                ['spock-node=', 'spock-num-nodes=', 'spock-tx-mix=',
                 'spock-no-hid', 'spock-no-delta-apply',
                 'no-data', 'data-only',
                 'initialize', 'fillfactor=', 'scale=',
                 'foreign-keys', 'index-tablespace=',
                 'partitions=', 'partition-method=',
                 'tablespace=', 'unlogged-tables',
                 'client=', 'connect', 'jobs=', 'log',
                 'latency-limit=', 'protocol=', 'no-vacuum',
                 'progress=', 'report-per-command', 'rate=',
                 'transactions=', 'time=', 'aggregate-interval=',
                 'failures-detailed', 'log-prefix=', 'max-tries=',
                 'progress-timestamp', 'random-seed=',
                 'sampling-rate=', 'verbose-errors',
                 'debug', 'host=', 'port=', 'username=',
                ])
        except Exception as ex:
            print(str(ex), file = sys.stderr)
            sys.exit(2)
        
        for opt, val in opts:
            # ----
            # Options that need special attention
            # ----
            if opt in ['--spock-node',]:
                self.node = int(val)
            elif opt in ['--spock-num-nodes',]:
                self.num_nodes = int(val)
            elif opt in ['--spock-tx-mix',]:
                vals = val.split(',')
                if len(vals) != 3:
                    print("argument for --spock-tx-mix should be " +
                          "three numbers to use as probabilities",
                          file = sys.stderr)
                    print("for transaction profiles local@x,remote-A@y,"
                          "remote-TA@z.",
                          file = sys.stderr)
                    sys.exit(1)
                self.tx_local = vals[0]
                self.tx_remote_A = vals[1]
                self.tx_remote_TA = vals[2]
            elif opt in ['--spock-no-hid',]:
                self.no_hid = True
            elif opt in ['--spock-no-delta-apply',]:
                self.no_delta_apply = True
            elif opt in ['--no-data',]:
                self.no_data = True
            elif opt in ['--data-only',]:
                self.data_only = True
            elif opt in ['-i', '--initialize',]:
                self.is_init = True
            elif opt in ['-s', '--scale',]:
                self.scale = int(val)
            elif opt in ['--foreign-keys',]:
                self.have_fkeys = True

            # ----
            # Common options
            # ----
            elif opt in ['-d', '--debug', '-h', '--host',
                         '-p', '--port', '-U', '--username',]:
                self.pgbench_iopts.append(opt)
                if val != '':
                    self.pgbench_iopts.append(val)
                self.pgbench_opts.append(opt)
                if val != '':
                    self.pgbench_opts.append(val)

            # ----
            # Options that need to be handed to pgbench --initialize
            # ----
            elif opt in ['-F', '--fillfactor', '--foreign-keys',
                         '--index-tablespace',
                         '--partitions', '--partition-method',
                         '--tablespace', '--unlogged-tables',]:
                self.pgbench_iopts.append(opt)
                if val != '':
                    self.pgbench_iopts.append(val)

            # ----
            # Options that need to be handed to pgbench running the test
            # ----
            else:
                self.pgbench_opts.append(opt)
                if val != '':
                    self.pgbench_opts.append(val)
    
    def load_sql_scripts(self):
        self.sql_fname = {}
        pid = str(os.getpid())

        for s in ['local', 'remote-A', 'remote-TA', 'alter-TA', 'alter-H',
                  'check',]:
            fname = 'spockbench-' + s + '.sql'
            with importlib.resources.open_text(__package__, fname) as fd:
                script = fd.read()
                self.sql_fname[s] = os.path.join('/tmp', fname + '.' + pid)
                with open(self.sql_fname[s], 'w') as tfd:
                    self.tempfiles.append(self.sql_fname[s])
                    tfd.write(script)

    def cleanup(self):
        for fname in self.tempfiles:
            try:
                os.remove(fname)
            except Exception as ex:
                print(str(ex))

