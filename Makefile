PY ?= python
PIP ?= $(PY) -m pip
RUN ?= pl-$(shell date +%Y%m%d-%H%M)

.PHONY: help install test test-live doctor smoke eval sample replay dev api ui build serve demo fixtures visual clean

help:
	@echo "Persona-Fuzz targets:"
	@echo "  make install    install python + ui dependencies"
	@echo "  make test       deterministic test suite (no network)"
	@echo "  make test-live  live smoke tests (requires NEBIUS_API_KEY)"
	@echo "  make doctor     connectivity / model / tool-calling diagnostics"
	@echo "  make smoke      quick run (live when a key is present)"
	@echo "  make sample     quick forced-offline flagged sample"
	@echo "  make eval       full evaluation"
	@echo "  make replay     render a markdown replay of the sample"
	@echo "  make dev        API :8000 + UI :5173"
	@echo "  make build      build UI and serve a single process"
	@echo "  make demo       offline replay of the recorded sample"
	@echo "  make fixtures   rebuild fallback personas + flagged synthetic sample"
	@echo "  make visual     screenshot and overflow gate (API must be running)"

install:
	$(PIP) install -r requirements.txt
	cd ui && npm install

test:
	$(PY) -m pytest -q

test-live:
	$(PY) -m pytest -q -m live

doctor:
	$(PY) -m engine.cli doctor

smoke:
	$(PY) -m engine.cli run --quick --run-id $(RUN)

eval:
	$(PY) -m engine.cli run --full --run-id $(RUN)

sample:
	$(PY) -m engine.cli run --quick --offline --run-id sample

replay:
	$(PY) -m engine.cli replay sample

dev:
	$(PY) -m engine.cli serve --reload & cd ui && npm run dev

api:
	$(PY) -m engine.cli serve --reload

ui:
	cd ui && npm run dev

build:
	cd ui && npm run build

serve:
	$(PY) -m engine.cli serve

demo:
	$(PY) -m engine.cli replay sample
	$(PY) -m engine.cli serve

fixtures:
	$(PY) scripts/make_fixtures.py

visual:
	cd ui && node scripts/visual_check.mjs

clean:
	rm -rf .pytest_cache .hypothesis ui/dist
