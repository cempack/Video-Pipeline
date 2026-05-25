.PHONY: build install-py test serve doctor

BINARY := dist/video-factory

build:
	mkdir -p dist
	cd . && go build -ldflags="-s -w" -o $(BINARY) ./cmd/video-factory
	@echo "Built $(BINARY)"

install-py:
	pip install -e ".[dev]" --break-system-packages 2>/dev/null || pip install -e ".[dev]"

test:
	PYTHONPATH=src python3 -m pytest -q

serve: build
	./$(BINARY) serve

doctor: build
	./$(BINARY) doctor
