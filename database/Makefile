# Makefile for generic CO2 data and web display
#
# This Makefile and code directory is shared with the CO2 OU web server.
# Updates can manually be transferred between repositories.
# When updating, take care to keep it generic so that it can be a drop-in replacement.
#
# Installation-specific data can go in a separate directory.
#
# Requires simple info about unit deployment in a TSV (tab-separated CSV) file.
    # Default location for this file is ../manual/deploy_durations_tiered.tsv .
# Set the DATA_DIR or DEPLOY_DURATIONS_TIERED_TSV variable to override.

.PHONY: default all web

default: web

all: default # (more added throughout file)

# Important locations (can be overridden)
# --------------------------------------------------
DATA_DIR := ..
DB_DIR := .
WEB_PUB_DIR := out_web

# Cleaning
# --------------------------------------------------

.PHONY: clean distclean

# Removes git-ignored files
clean:
	git clean -Xf

# Removes git-ignored files AND directories (including Python virtualenv)
distclean:
	git clean -Xdf

# Database general
# --------------------------------------------------

DB_FILE := $(DB_DIR)/db.sqlite3

# Deploy data (tiered)
# --------------------------------------------------

DEPLOY_DURATIONS_TIERED_IMPORT_MARKER:=$(DB_DIR)/.mark_db_load_deploy_durations_tiered
DEPLOY_DURATIONS_TIERED_TSV := $(DATA_DIR)/manual/deploy_durations_tiered.tsv

$(DEPLOY_DURATIONS_TIERED_IMPORT_MARKER): $(wildcard $(DEPLOY_DURATIONS_TIERED_TSV)) ./bin/import-deploy-durations-tiered.sh
	mkdir -p $(@D)
	./bin/import-deploy-durations-tiered.sh $(DB_FILE) $(DEPLOY_DURATIONS_TIERED_TSV) && touch $@

web: $(DEPLOY_DURATIONS_TIERED_IMPORT_MARKER)

# Pings
# --------------------------------------------------

PING_IMPORT_MARKER:=$(DB_DIR)/.mark_db_load_pings
PING_FILES:=$(wildcard $(DATA_DIR)/*/var/pings/pings-*.tsv)

$(PING_IMPORT_MARKER): $(PING_FILES) bin/import-pings.sh
	mkdir -p $(@D)
	./bin/import-pings.sh $(DB_FILE) $(PING_FILES) && touch $@

all: $(PING_IMPORT_MARKER)

# CO2 readings
# --------------------------------------------------

CO2_IMPORT_MARKER:=$(DB_DIR)/.mark_db_load_co2_readings
CO2_READING_FILES:=$(wildcard $(DATA_DIR)/co2unit-*/data/readings/readings-*.tsv)

$(CO2_IMPORT_MARKER): $(CO2_READING_FILES) bin/import-co2-readings.sh
	mkdir -p $(@D)
	./bin/import-co2-readings.sh $(DB_FILE) $(CO2_READING_FILES) && touch $@

all: $(CO2_IMPORT_MARKER)

# Error logs
# --------------------------------------------------

ERROR_IMPORT_MARKER:=$(DB_DIR)/.mark_db_load_error_logs
ERROR_LOG_FILES:=$(wildcard $(DATA_DIR)/co2unit-*/errors/errors-*.txt)

$(ERROR_IMPORT_MARKER): $(ERROR_LOG_FILES) bin/import-error-logs.sh
	mkdir -p $(@D)
	./bin/import-error-logs.sh $(DB_FILE) $(ERROR_LOG_FILES) && touch $@

all: $(ERROR_IMPORT_MARKER)

# Plots and analysis with Python / Jupyter
# --------------------------------------------------

PYTHON_VENV := python/.venv

python/requirements-freeze.txt: python/requirements-top-level.txt
	[ -d "$(PYTHON_VENV)" ] || virtualenv $(PYTHON_VENV) --python=python3
	. $(PYTHON_VENV)/bin/activate && pip install -r $< && pip freeze -r $< > $@

$(PYTHON_VENV): python/requirements-freeze.txt
	[ -d "$(PYTHON_VENV)" ] || virtualenv $(PYTHON_VENV) --python=python3
	. $(PYTHON_VENV)/bin/activate && pip install -r $< && touch $(PYTHON_VENV)

# Update frozen requirements on distclean
distclean: python/requirements-freeze.txt

# Pings info for the web
# --------------------------------------------------

.PHONY: pings_summary_web
web: pings_summary_web

pings_summary_web: \
    $(WEB_PUB_DIR)/pings_summary.html \
    $(WEB_PUB_DIR)/pings_all_tiered.svg \


$(WEB_PUB_DIR)/pings_summary.html: \
    $(DEPLOY_DURATIONS_TIERED_IMPORT_MARKER) $(PING_IMPORT_MARKER) \
    templates_web/pings_summary.html python/pings_summary.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/pings_summary.py $(DB_FILE) templates_web/pings_summary.html > $@

$(WEB_PUB_DIR)/pings_all_tiered.svg: \
    $(DEPLOY_DURATIONS_TIERED_IMPORT_MARKER) $(PING_IMPORT_MARKER) \
    python/pings_plot_tiered.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/pings_plot_tiered.py $(DB_FILE) $@ # --xmin=2020-07-01 --xmax=2020-08-01 --min-tier=10

# CO2 info for the web
# --------------------------------------------------

.PHONY: co2_summary_web
web: co2_summary_web

co2_summary_web: \
    $(WEB_PUB_DIR)/co2_summary.html \
    $(WEB_PUB_DIR)/co2_tiered_recent_hires.svg \
    $(WEB_PUB_DIR)/co2_tiered_all_hires.svg \


$(WEB_PUB_DIR)/co2_summary.html: \
    templates_web/co2_summary.html \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	cp $< $@

$(WEB_PUB_DIR)/co2_tiered_all_hires.svg: \
    $(DEPLOY_DURATIONS_TIERED_IMPORT_MARKER) $(CO2_IMPORT_MARKER) \
    python/co2_plot_tiered.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/co2_plot_tiered.py $(DB_FILE) $@ # --same-ranges --co2-max 10000 --dpi 600

$(WEB_PUB_DIR)/co2_tiered_recent_hires.svg: \
    $(DEPLOY_DURATIONS_TIERED_IMPORT_MARKER) $(CO2_IMPORT_MARKER) \
    python/co2_plot_tiered.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/co2_plot_tiered.py --recent-days 14 $(DB_FILE) $@
