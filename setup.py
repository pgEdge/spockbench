####################################################################
######          Copyright (c)  2023-2025 PGEDGE           ##########
####################################################################

from distutils.core import setup

setup(
    name = 'spockbench',
    description = 'Spock benchmark based on pgbench',
    version = '1.0',
    author = 'Jan Wieck',
    author_email = 'jan@wi3ck.info',
    url = None,
    license = 'TBD',
    packages = ['spockbench'],
    package_data = {'spockbench': ['spockbench-local.sql',
                                   'spockbench-remote-A.sql',
                                   'spockbench-remote-TA.sql',
                                   'spockbench-alter-H.sql',
                                   'spockbench-alter-TA.sql',
                                   'spockbench-check.sql',]},
    scripts = ['spockbench/spockbench',
               'spockbench/spockbench-check'],
)
