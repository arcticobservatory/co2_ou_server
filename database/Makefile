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

# Deploy data
# --------------------------------------------------

DEPLOY_IMPORT_MARKER:=$(DB_DIR)/.mark_db_load_deploy_durations
DEPLOY_DURATIONS_TSV := $(DATA_DIR)/manual/deploy_durations.tsv

$(DEPLOY_IMPORT_MARKER): $(wildcard $(DEPLOY_DURATIONS_TSV)) | $(DEPLOY_DURATIONS_TSV)
	./bin/import-deploy-durations.sh $(DB_FILE) < $(DEPLOY_DURATIONS_TSV) && touch $@

$(DEPLOY_DURATIONS_TSV):
	@echo MANUAL INTERVENTION REQUIRED
	@echo The deployment_durations table must be added manually.
	@echo Options
	@echo 	1. Create the table in the database and create a marker file $(DEPLOY_IMPORT_MARKER)
	@echo 	2. Create a $(DEPLOY_DURATIONS_TSV) file
	@echo 	2a. If the file already exists, set the DEPLOY_DURATIONS_TSV variable to point to it
	@echo 	3. Pipe appropriate TSV data into the script bin/import-deploy-durations.sh
	exit 1

all: $(DEPLOY_IMPORT_MARKER)

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
    $(WEB_PUB_DIR)/pings_all.svg \


$(WEB_PUB_DIR)/pings_summary.html: \
    $(DEPLOY_IMPORT_MARKER) $(PING_IMPORT_MARKER) \
    templates_web/pings_summary.html python/pings_summary.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/pings_summary.py $(DB_FILE) templates_web/pings_summary.html > $@

$(WEB_PUB_DIR)/pings_all.svg: \
    $(DEPLOY_IMPORT_MARKER) $(PING_IMPORT_MARKER) \
    python/pings_plot.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/pings_plot.py $(DB_FILE) $@

# CO2 info for the web
# --------------------------------------------------

.PHONY: co2_summary_web
web: co2_summary_web

co2_summary_web: \
    $(WEB_PUB_DIR)/co2_summary.html \
    $(WEB_PUB_DIR)/co2_all_hires.png \
    $(WEB_PUB_DIR)/co2_recent_hires.png \


$(WEB_PUB_DIR)/co2_summary.html: \
    templates_web/co2_summary.html \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	cp $< $@

$(WEB_PUB_DIR)/co2_all_hires.png: \
    $(DEPLOY_IMPORT_MARKER) $(CO2_IMPORT_MARKER) \
    python/co2_plot.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/co2_plot.py --same-ranges --co2-max 6000 --dpi 600 $(DB_FILE) $@

$(WEB_PUB_DIR)/co2_recent_hires.png: \
    $(DEPLOY_IMPORT_MARKER) $(CO2_IMPORT_MARKER) \
    python/co2_plot.py \
    | $(PYTHON_VENV)
	mkdir -p $(@D)
	. $(PYTHON_VENV)/bin/activate && python python/co2_plot.py --recent-days 14 --dpi 600 $(DB_FILE) $@
