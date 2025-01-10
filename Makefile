.PHONY: all clean env env-dev  build-conda-base build-conda-gui  gui-deps gui-build gui-clean build-pip install test test-pip test-conda

# Variables
CONDA_ENV_NAME = geocover-qa-dev
PYTHON_VERSION = 3.11
PACKAGE_NAME = geocover-qa

# Check if we're in a conda environment
CONDA_PREFIX ?= $(shell echo $$CONDA_PREFIX)
ifdef CONDA_PREFIX
    # We're in an activated environment, use direct commands
    CONDA_RUN =
else
    # We're not in an environment, use conda run
    CONDA_RUN = conda run -n $(CONDA_ENV_NAME)
endif

# Help target
help:
	@echo "Available targets:"
	@echo "  make all         - Create environment and install package"
	@echo "  make clean       - Remove build artifacts"
	@echo "  make env         - Create basic conda environment"
	@echo "  make env-dev     - Create development environment"
	@echo "  make build-conda - Build all conda packages"
	@echo "  make build-pip   - Build pip package"
	@echo "  make gui-deps    - Install depencies for building PyQt application"
	@echo "  make gui-build   - Build standalone PyQt GUI application"
	@echo "  make install     - Install package in development mode"
	@echo "  make test        - Run tests"
	@echo "  make test-pip    - Test pip package installation"
	@echo "  make test-conda  - Test conda package installation"
	@echo "  make full-check  - Run full build and test cycle"


all: env install test

# Full build and test cycle
full-check: clean build-pip build-conda test-pip test-conda


lint:
	ruff format src/
# Create basic conda environment
env:
	conda config --set solver classic
	conda create -n $(CONDA_ENV_NAME) python=$(PYTHON_VERSION) -y
	$(CONDA_RUN) conda install --solver=classic -c conda-forge -c default  -y geopandas matplotlib pandas gdal fiona numpy loguru pyqt

# Create development environment with all tools
env-dev: env
	$(CONDA_RUN) conda install   -c conda-forge -c default -y ruff flake8 twine conda-build pip build pytest
	$(CONDA_RUN) pip install -e ".[dev,gui]"
	$(CONDA_RUN) python -m pip install --upgrade build

# Build base conda package without GUI
build-conda-base:
	$(CONDA_RUN) conda build . --output-folder dist/conda

# Build GUI conda package
build-conda-gui:
	$(CONDA_RUN) conda build .conda/gui --output-folder dist/conda

# Build all conda packages
build-conda: build-conda-base build-conda-gui

# Build pip package
build-pip:
	$(CONDA_RUN) python -m build --sdist --wheel --outdir dist/pip

gui-deps:
	$(CONDA_RUN) pip install pyinstaller
	$(CONDA_RUN) pip install -e ".[gui]"


# Build standalone GUI application
gui-build:
	$(CONDA_RUN) pyinstaller gui/geocover-qa.spec --distpath dist/gui --workpath build/gui
gui-clean:
	rm -rf build/gui
	rm -rf dist/gui
	rm -rf *.spec



# Full GUI build process
gui: gui-deps gui-build

# Install package in development mode
install:
	$(CONDA_RUN) pip install -e ".[dev,gui]"

# Run tests with pytest
test:
	$(CONDA_RUN) pytest tests/ -v

# Test pip package installation
test-pip:
	pip install dist/pip/$(PACKAGE_NAME)-*.whl
	pytest tests/ -v
	pip uninstall -y $(PACKAGE_NAME)

# Test conda package installation
test-conda:
	$(CONDA_RUN) conda install -y --use-local $(PACKAGE_NAME)
	$(CONDA_RUN) pytest tests/ -v
	$(CONDA_RUN) conda remove -y $(PACKAGE_NAME)



# Clean build artifacts and cache
clean: gui-clean
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf **/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage