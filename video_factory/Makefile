.PHONY: build prepare-embed test setup doctor

BINARY := dist/video-factory

prepare-embed:
	bash scripts/prepare-embed.sh

build: prepare-embed
	mkdir -p dist
	go build -ldflags="-s -w" -o $(BINARY) ./cmd/video-factory
	@echo "Built $(BINARY) (embeds Python engine; first run auto-installs deps)"

test:
	PYTHONPATH=src python3 -m pytest -q

heavy-test: build
	bash scripts/heavy-test.sh

setup: build
	./$(BINARY) setup

doctor: build
	./$(BINARY) doctor

serve: build
	./$(BINARY) serve

release: prepare-embed
	GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o dist/video-factory-linux-amd64 ./cmd/video-factory
	GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o dist/video-factory-darwin-arm64 ./cmd/video-factory
	GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o dist/video-factory-darwin-amd64 ./cmd/video-factory
	GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o dist/video-factory-windows-amd64.exe ./cmd/video-factory
	@echo "Release binaries in dist/"
