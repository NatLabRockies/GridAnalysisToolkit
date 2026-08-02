.PHONY: test fixture-deck fixture-deck-sienna fixture-deck-all regen-snapshots \
        sienna-image-v4 sienna-image-v5 sienna-fixture-v4 sienna-fixture-v4-multi sienna-fixture-v5 sienna-fixture-pjm5

PYTHON ?= python
UV ?= uv
SIENNA_OUT_V4 := example_data/sienna/v4
SIENNA_OUT_V4_MULTI := example_data/sienna/v4_multifile
SIENNA_OUT_V5 := example_data/sienna/v5

test:
	$(PYTHON) -m pytest tests/ -v

# Visual review decks — for local eyeballing after plotting/reporting/
# aggregation changes, not a pytest test. See tests/visual/generate_fixture_deck.py
# for fixture resolution order (env vars, ~/.gat-test-data, example_data).
fixture-deck:
	$(PYTHON) tests/visual/generate_fixture_deck.py --model-type plexos

fixture-deck-sienna:
	$(PYTHON) tests/visual/generate_fixture_deck.py --model-type sienna

fixture-deck-all:
	$(PYTHON) tests/visual/generate_fixture_deck.py --all

regen-snapshots:
	$(PYTHON) -m pytest tests/handlers/test_plexos_regression.py tests/handlers/test_sienna_regression.py --force-regen

sienna-image-v4:
	docker build --build-arg SIENNA_VERSION=4 -t gat-sienna:v4 docker/sienna

sienna-image-v5:
	docker build --build-arg SIENNA_VERSION=5 -t gat-sienna:v5 docker/sienna

sienna-fixture-v4: sienna-image-v4
	mkdir -p $(SIENNA_OUT_V4)
	docker run --rm -v "$(PWD)/$(SIENNA_OUT_V4):/output" gat-sienna:v4

# Two-file fixture for exercising the multi-file aggregator path. Runs two
# overlapping PSI sub-simulations and writes simulation_store.h5 +
# simulation_store_2.h5 to example_data/sienna/v4_multifile/.
sienna-fixture-v4-multi: sienna-image-v4
	mkdir -p $(SIENNA_OUT_V4_MULTI)
	docker run --rm -e SIM_FILES=2 \
		-v "$(PWD)/$(SIENNA_OUT_V4_MULTI):/output" gat-sienna:v4

sienna-fixture-v5: sienna-image-v5
	mkdir -p $(SIENNA_OUT_V5)
	docker run --rm -v "$(PWD)/$(SIENNA_OUT_V5):/output" gat-sienna:v5

# PJM 5-bus long-horizon fixture (issue #18): same image as v4, selected
# via SIM_SYSTEM=pjm5 — two synthetic zones, synthetic annual profiles.
# Default SIM_STEPS=365 for the annual solve; override for smoke tests,
# e.g. `make sienna-fixture-pjm5 SIM_STEPS=3`.
SIM_STEPS ?= 365
SIENNA_OUT_PJM5 := example_data/sienna/pjm5
sienna-fixture-pjm5: sienna-image-v4
	mkdir -p $(SIENNA_OUT_PJM5)
	docker run --rm -e SIM_SYSTEM=pjm5 -e SIM_STEPS=$(SIM_STEPS) \
		-v "$(PWD)/$(SIENNA_OUT_PJM5):/output" gat-sienna:v4

