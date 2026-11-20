PY=python3
.PHONY: data test api web demo
data:      ## build walk graph + GTFS CSA artifacts
	$(PY) -m ledger.pipeline.build
test:
	$(PY) -m pytest
api:
	$(PY) -m uvicorn ledger.api.app:app --port 8000
web:
	cd web && npm run dev
demo:      ## offline demo: cached LLM, real artifacts
	LLM_MODE=cached $(PY) -m uvicorn ledger.api.app:app --port 8000 & cd web && npm run dev
