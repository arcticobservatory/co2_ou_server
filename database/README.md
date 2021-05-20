CO2 Observation Unit Database Scripts
==================================================

These are scripts to analyze data from a
CO2 sensor, or "Observation Unit",
developed at UiT The Arctic University of Norway
as part of the Distributed Arctic Observatory project.
These Observation Units are described in the paper:

Murphy et al.
"Experiences Building and Deploying
 Wireless Sensor Nodes for the Arctic Tundra,"
in The 21st IEEE/ACM International Symposium on
   Cluster, Cloud and Internet Computing (CCGrid 2021).
Melbourne Australia, May 2021.

This directory contains scripts to import the collected data
into a SQLite database and to generate plots from the data.
These scripts are designed to work with generic CO2 data
as described in the [Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md) document,
with optional deployment-specific information.
It should also be possible to make a copy to be kept with the
data itself that is extended with more custom scripts.

Repositories and Documentation Associated with this Project
------------------------------------------------------------

- [co2_ou_device](https://github.com/arcticobservatory/co2_ou_device) repo
    --- Code and documentation for the observation unit itself

    - [Parts List](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-parts-list.md)
        --- parts used to build the observation units
    - [Circuit Schematic](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-schematic-v1.pdf)
        --- diagram of hardware and pin connections
    - [FiPy/Observation Unit Setup](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-fipy-setup.md)
        --- guide to installing the code on a FiPy and configuring the OU
    - [Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md)
        --- OU naming, data directory structure, and data file formats

- [co2_ou_server](https://github.com/arcticobservatory/co2_ou_server) repo
    --- Code and documentation for the companion server

    - [Database Scripts](https://github.com/arcticobservatory/co2_ou_server/tree/master/database)
        --- Shell scripts that import the text-based CO2 data into a
            SQLite database for analysis, plus Python scripts to generate plots

Input Data
--------------------------------------------------

These scripts default to assuming that they live in a `database/` subdirectory
of the collected data itself (e.g. the server's `remote_data/` directory).
So the default data directory is `../`

When distributed with the server code, these scripts live in a `database/`
subdirectory of the server code repository.
And so the data dir is `../remote_data/`

To set the data directory, set the DATA_DIR env/Make variable.

For information on the directory structure and file formats of
Observation Data, see the
[Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md)
document in the CO2 OU device code repository.

In this Directory
--------------------------------------------------

Tasks are controlled by a Makefile.
The default target should
(1) create a database,
(2) import all data,
(3) create a Python virtualenv,
(4) install Python dependencies, and
(5) generate plots and web pages to display them.
This can be run periodically by a cron job on the server
as an easy way to have a "live" results page.

Source files and directories:

- `Makefile` --- GNU Make script with many tasks, see code for details
- `bin/` --- shell scripts for creating database tables and importing data
- `python/` --- Python scripts for creating plots from the data
- `templates_web/` --- templates for web pages to display generated plots.

Output directories and files:

- `db.sqlite3` --- the database itself.
        Can be placed in a different directory by setting the
        DB_DIR env/Make variable.

- `out_web/` --- generated plots and web pages to display them.
        Can be overriden by setting the WEB_PUB_DIR env/Make variable.

An example of overriding input and output directories is the 
[make-summaries.sh](https://github.com/arcticobservatory/co2_ou_server/blob/master/scripts/make-summaries.sh)
script in the server code.
It overrides the data directory to be the server's `remote_data/` directory,
the database directory to `var/` and the web directory to `var/pub/`.

Adding Deployment Information
--------------------------------------------------

The plot scripts should work with just the raw data,
getting OU IDs and nicknames from the data itself.
However, it is much more useful to see data plotted based on where the OUs
were actually deployed.

These scripts create a deployment table in the database called
`deploy_durations_tiered` that looks something like this:

| unit_id              | nickname    | site        | tier | status    | start_ts            | end_ts              | note                         |
|----------------------|-------------|-------------|-----:|-----------|---------------------|---------------------|------------------------------|
| co2unit-30aea42a5140 | test_unit   | field_spare |    8 | lab_check |                     | 2019-08-01T00:00:00 |                              |
| co2unit-30aea42a5140 | test_unit   | field_spare |    8 | en_route  | 2019-08-01T00:00:00 | 2019-08-13T12:00:00 | with Mike on flight to Vadsø |
| co2unit-30aea42a5268 | varanger-01 | vj_re_sn_3  |   23 | lab_check |                     | 2019-08-01T00:00:00 |                              |
| co2unit-30aea42a5268 | varanger-01 | vj_re_sn_3  |   23 | en_route  | 2019-08-01T00:00:00 | 2019-08-13T12:00:00 |                              |
| co2unit-30aea42a5268 | varanger-01 | vj_re_sn_3  |   23 | deployed  | 2019-08-13T12:00:00 | 2019-09-26T08:00:00 |                              |

This table starts out empty but you can populate it manually
or create a tab-delimited file for import (see below).

Each row of this table represents a duration where the unit was deployed and
collecting data associated with a given site.
There can also be rows for time spent
in transit to and from the given site (`status=en_route`),
or testing in the lab before or after deployment (`status=lab_check`).
The plots will include those periods in a subdued style
(lighter shading or dotted/dashed lines).

The `unit_id`, `nickname`, and `site` fields represent the three OU names/IDs
as explained in the [Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md)
document.

The `tier` field is used for sort order when querying data and making plots.
Plots are displayed with higher tiers at the top of the plot,
and you can set a minimum tier on the command line.
For example, we used tier 0 for running in the lab on a desk,
8 for backyard deployment, and 10+ for actual deployment in
reverse display order.
Then, to plot only real-world deployment,
we pass `--min-tier=10` to the plotting script.
`lab_check` and `en_route` periods should use the same site and tier
as the actual deployment period.

Timestamps should be in ISO timestamp or date format,
e.g. 2019-08-13T12:34:45 or just 2019-08-13.

To recap, the SQLite table specification looks like this:

```sql
CREATE TABLE deploy_durations_tiered (
    unit_id     TEXT,       " the OU's hardware ID, e.g. co2unit-30aea42a5268
    nickname    TEXT,       " the OU's nickname, e.g. varanger-01
    site        TEXT,       " the name of the site where the OU was deployed
    tier        INTEGER,    " sort order / importance
    status      TEXT,       " one of 'deployed', 'en_route', or 'lab_check'
    start_ts    TEXT,       " starting timestamp in ISO format, e.g. 2019-08-13T12:34:45
    end_ts      TEXT,       " ending timestamp, also in ISO format
    note        TEXT        " free-form additional notes
);
```

### Deployment Information as a Tab-Delimited File

By default the `deploy_durations_tiered` table is populated from a
tab-separated-values (CSV with tab delimiters) file
in the `manual/` subdirectory of the data directory (if it exists):
`manual/deploy_durations_tiered.tsv`

That way it can be kept with the collected data.
To use a specific file, set the DEPLOY_DURATIONS_TIERED_TSV env/Make variable.

The file is simply a tab-separated table with headers.
For additional human-readability, you can add blank spaces to separate groups
of deployments, and you can add comment lines marked with a '#'.
For example:

```
unit_id	nickname	site	tier	status	start_ts	end_ts	note
co2unit-30aea42a5140	test_unit	field_spare	8	lab_check		2019-08-01T00:00:00	
co2unit-30aea42a5140	test_unit	field_spare	8	en_route	2019-08-01T00:00:00	2019-08-13T12:00:00	with Mike on flight to Vadsø
							
co2unit-30aea42a5268	varanger-01	vj_re_sn_3	23	lab_check		2019-08-01T00:00:00	
co2unit-30aea42a5268	varanger-01	vj_re_sn_3	23	en_route	2019-08-01T00:00:00	2019-08-13T12:00:00	
co2unit-30aea42a5268	varanger-01	vj_re_sn_3	23	deployed	2019-08-13T12:00:00	2019-09-26T08:00:00	

# IMPORTANT DATES							
#							
# 2019-08-13 (through day)	First deployment						
# 2019-09-26 (through day)	Update: switch FiPys						
```

The blank and comment lines will be filtered out on import.
