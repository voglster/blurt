# Blurt Development TODO

**Current Status (Latest Update):** Phase 1 & 2 Complete ✅
- **Code Quality**: Full tooling setup, 48% test coverage, clean architecture
- **Daemon Management**: Proper daemonization, XDG compliance, PID management
- **Next Priority**: Phase 3 - Python packaging for `pip install blurt`

## Phase 1: Code Quality & Development Tools ✅ COMPLETED

> **✅ Phase 1 Complete: Solid foundation established!**
>
> - Full code quality tooling (ruff, mypy, bandit, pre-commit)
> - 48% test coverage with comprehensive unit tests
> - Clean file structure and naming conventions
> - Proper daemon implementation with XDG compliance

## Phase 1.1: Code Quality & Development Tools ✅ COMPLETED

### 1.1.1 Code Formatting & Linting ✅
- [x] Add `ruff` for fast Python linting and formatting
  - [x] Configure `ruff.toml` or `pyproject.toml` rules
  - [x] Run `ruff check` and `ruff format` on codebase
  - [x] Fix all linting issues
- [x] Set up `pre-commit` hooks
  - [x] Install pre-commit framework
  - [x] Configure `.pre-commit-config.yaml`
  - [x] Include ruff, type checking, and other quality checks
  - [x] Test pre-commit hooks work locally

### 1.1.2 Type Checking & Testing ✅
- [x] Add comprehensive type hints throughout codebase
  - [x] Use `mypy` for static type checking
  - [x] Configure `mypy.ini` or `pyproject.toml` settings
  - [x] Fix all type errors
- [x] Set up testing framework
  - [x] Choose testing framework (pytest ✅)
  - [x] Write unit tests for core functionality (48% coverage)
  - [x] Add integration tests for CLI commands
  - [x] Set up test coverage with `coverage.py`
  - [ ] Aim for >80% code coverage (currently 48%)

### 1.1.3 Dead Code & Security ✅
- [x] Use `vulture` to find dead/unused code
  - [x] Remove unused imports and functions
  - [x] Clean up any legacy code from tab_voice era
- [x] Security scanning
  - [x] Use `bandit` for security issue detection
  - [x] Fix any security warnings
  - [x] Review dependencies for known vulnerabilities

### 1.1.4 Documentation & Code Quality 🔄 IN PROGRESS
- [x] Add comprehensive docstrings
  - [x] All public functions and classes
  - [x] Follow Google or NumPy docstring style
  - [x] Use `pydocstyle` to enforce consistency
- [ ] Code complexity analysis
  - [ ] Use `radon` to check cyclomatic complexity
  - [ ] Refactor overly complex functions
- [x] Import organization
  - [x] Use `isort` to organize imports consistently
  - [x] Configure to work with ruff

### 1.1.5 Development Workflow ✅
- [x] Create development scripts (via uv commands)
- [x] Update `pyproject.toml` with dev dependencies

### 1.1.6 CI/CD Quality Gates
- [ ] GitHub Actions workflow for quality checks
  - [ ] Run ruff, mypy, tests on every PR
  - [ ] Block merges if quality checks fail
  - [ ] Generate coverage reports
- [ ] Add quality badges to README
  - [ ] Build status, coverage %, PyPI version
  - [ ] Code quality score if using external service

### 1.1.7 Configuration Files ✅
- [x] `.pre-commit-config.yaml`
- [x] `mypy.ini` or mypy config in `pyproject.toml`
- [x] `ruff.toml` or ruff config in `pyproject.toml`
- [ ] `.github/workflows/quality.yml`
- [x] Update `.gitignore` for development artifacts

### 1.1.8 Code Structure Refactoring ✅ COMPLETED
- [x] Remove "simple" prefixes from file and class names
- [x] Rename `simple_audio.py` → `audio_recorder.py`
- [x] Rename `simple_hotkey.py` → `hotkey_handler.py`
- [x] Rename `SimpleAudioRecorder` → `AudioRecorder`
- [x] Rename `SimpleHotkeyHandler` → `HotkeyHandler`
- [x] Delete unused legacy files (X11/async implementations)
- [x] Update all imports and references

## Phase 2: CLI & Process Management ✅ MOSTLY COMPLETED

### 2.1 Basic CLI Structure ✅
- [x] Create `cli.py` with start/stop/restart/status/install commands
- [x] Basic PID file management

### 2.2 Daemon Mode ✅ COMPLETED
- [x] Implement proper daemon process
  - [x] Fork process and detach from terminal
  - [x] Redirect stdout/stderr to log file
  - [x] Handle signals properly (SIGTERM, SIGINT)
- [x] Log file in `~/.config/blurt/blurt.log`
- [ ] Rotate logs when they get too big
- [ ] Add `--foreground` flag for debugging

### 2.3 Process Management ✅ COMPLETED
- [x] Improve PID file handling
  - [x] XDG Base Directory compliance (PID in $XDG_RUNTIME_DIR)
  - [x] Fallback to /tmp with UID when XDG_RUNTIME_DIR unavailable
  - [x] Check if PID actually belongs to running process
  - [x] Clean up stale PID files automatically
- [x] Better error messages
  - [x] "Already running" with PID information
  - [x] "Not running" clear status
  - [x] Process not found cleanup
- [ ] Add `blurt logs` command to tail log file

### 2.4 Directory Structure & Configuration
- [x] Move from `~/.config/tab_voice/` to `~/.config/blurt/`
- [x] **Fix XDG Base Directory compliance**:
  - [x] Config: `~/.config/blurt/config.toml` ✅
  - [x] Data/Models: `~/.local/share/blurt/models/`
  - [x] Logs: `~/.local/state/blurt/blurt.log`
  - [x] Cache: `~/.cache/blurt/` (for temp downloads)
  - [x] Update model path resolution in config.py
  - [x] Updated speech_recognizer.py to use new paths
- [ ] Validate config on startup
- [ ] Add config options:
  ```toml
  [hotkeys]
  start_recording = "<ctrl>+<space>"

  [daemon]
  log_level = "info"
  log_file = "~/.local/state/blurt/blurt.log"

  [model]
  data_dir = "~/.local/share/blurt"
  cache_dir = "~/.cache/blurt"
  ```
- [ ] Add `blurt config` command to show current config

## Phase 3: Installation & Packaging (CURRENT PRIORITY 🚀)

### 3.1 Python Package Structure
- [ ] Create proper package structure:
  ```
  blurt/
  ├── pyproject.toml          # Modern Python packaging
  ├── setup.py                # Fallback for older pip
  ├── README.md               # PyPI description
  ├── LICENSE                 # Required for PyPI
  ├── MANIFEST.in             # Include non-Python files
  ├── blurt/
  │   ├── __init__.py         # Package init with __version__
  │   ├── cli.py              # CLI entry point
  │   ├── daemon.py           # Background service
  │   ├── audio/
  │   ├── hotkeys/
  │   └── ...
  └── blurt/resources/        # Package data
      └── sounds/
  ```
- [ ] Update imports after rename
- [ ] Add version management (`__version__`)

### 2.2 PyPI Packaging Files

#### pyproject.toml
- [ ] Create modern `pyproject.toml`:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [project]
  name = "blurt"
  version = "0.1.0"
  description = "Push-to-talk voice transcription for Linux"
  readme = "README.md"
  license = {file = "LICENSE"}
  authors = [
      {name = "Your Name", email = "your.email@example.com"},
  ]
  classifiers = [
      "Development Status :: 3 - Alpha",
      "Environment :: X11 Applications :: Gnome",
      "Intended Audience :: Developers",
      "License :: OSI Approved :: MIT License",
      "Operating System :: POSIX :: Linux",
      "Programming Language :: Python :: 3",
      "Programming Language :: Python :: 3.12",
      "Topic :: Multimedia :: Sound/Audio :: Speech",
      "Topic :: Utilities",
  ]
  keywords = ["voice", "transcription", "speech-to-text", "accessibility"]
  requires-python = ">=3.12"
  dependencies = [
      "numpy>=2.3.0",
      "pvrecorder>=1.2.7",
      "pynput>=1.8.1",
      "python-xlib>=0.33",
      "tomli-w>=1.2.0",
      "vosk>=0.3.45",
  ]

  [project.scripts]
  blurt = "blurt.cli:main"

  [project.urls]
  Homepage = "https://github.com/voglster/blurt"
  Repository = "https://github.com/voglster/blurt.git"
  Issues = "https://github.com/voglster/blurt/issues"
  ```

#### MANIFEST.in
- [ ] Include non-Python files:
  ```
  include README.md
  include LICENSE
  include CHANGELOG.md
  recursive-include blurt/resources *
  recursive-include blurt/sounds *.wav
  ```

#### setup.py (fallback)
- [ ] Minimal setup.py for compatibility:
  ```python
  from setuptools import setup
  setup()
  ```

### 2.3 PyPI Metadata & Requirements

#### Package Info
- [ ] Choose and add license (MIT recommended)
- [ ] Write proper package description
- [ ] Add classifiers for discoverability
- [ ] Set up author/maintainer info
- [ ] Add keywords for search

#### Dependencies
- [ ] Pin minimum versions of all dependencies
- [ ] Test with fresh virtual environment
- [ ] Document system requirements (X11, audio)
- [ ] Handle optional dependencies gracefully

### 2.4 PyPI Account & Upload

#### PyPI Setup
- [ ] Create PyPI account
- [ ] Set up 2FA
- [ ] Generate API token
- [ ] Create `.pypirc` file:
  ```ini
  [distutils]
  index-servers = pypi

  [pypi]
  username = __token__
  password = pypi-your-api-token-here
  ```

#### Build & Upload Tools
- [ ] Use uv for building: `uv build`
- [ ] Test build artifacts in `dist/`
- [ ] Set up PyPI token: `export UV_PUBLISH_TOKEN=pypi-your-token`
- [ ] Upload to TestPyPI first:
  ```bash
  uv publish --publish-url https://test.pypi.org/legacy/
  ```
- [ ] Test install from TestPyPI:
  ```bash
  pip install --index-url https://test.pypi.org/simple/ blurt
  ```
- [ ] Upload to real PyPI: `uv publish`

### 2.5 Version Management & Release Automation
- [ ] Set up semantic versioning (0.1.0, 0.1.1, etc.)
- [ ] Create `blurt/__init__.py` with `__version__`
- [ ] Sync version between `pyproject.toml` and `__init__.py`
- [ ] Create release automation script:

#### `scripts/release.sh`
```bash
#!/bin/bash
# Usage: ./scripts/release.sh [major|minor|patch]
# Default: patch

BUMP_TYPE=${1:-patch}

# Get current version from __init__.py
CURRENT_VERSION=$(grep "__version__" blurt/__init__.py | sed 's/__version__ = "\(.*\)"/\1/')

if [ -z "$CURRENT_VERSION" ]; then
    echo "❌ Could not find current version in blurt/__init__.py"
    exit 1
fi

echo "Current version: $CURRENT_VERSION"

# Parse version (assumes semantic versioning: X.Y.Z)
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump version based on type
case $BUMP_TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "❌ Invalid bump type: $BUMP_TYPE (use: major, minor, patch)"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "🚀 Bumping $BUMP_TYPE: $CURRENT_VERSION → $NEW_VERSION"

# 1. Update version in files
sed -i "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" blurt/__init__.py
sed -i "s/version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml

# 2. Commit all changes
git add .
git commit -m "Release v$NEW_VERSION"

# 3. Create and push tag
git tag "v$NEW_VERSION"
git push origin main
git push origin "v$NEW_VERSION"

echo "✅ Released v$NEW_VERSION! GitHub Actions will handle PyPI upload."
```


### 2.6 Post-Install Setup
- [ ] Auto-download Vosk model on first run
  - [ ] Progress bar for download
  - [ ] Verify checksum
  - [ ] Handle download failures gracefully
- [ ] Create config directory structure
- [ ] Copy default sounds to user directory


## Phase 3: User Experience

### 3.1 Better Audio Feedback
- [ ] Find/create better quality sounds
- [ ] Add config option to disable sounds
- [ ] Volume control in config
- [ ] Different sounds for errors

### 3.2 Error Handling
- [ ] Microphone not found
  - [ ] List available devices
  - [ ] Suggest solutions
- [ ] Model download failures
  - [ ] Retry mechanism
  - [ ] Manual download instructions
- [ ] Hotkey conflicts
  - [ ] Detect if hotkey is already bound
  - [ ] Suggest alternatives

### 3.3 Status & Feedback
- [ ] Add `--verbose` flag for debugging
- [ ] System notification on start/stop (optional)
- [ ] Better console output formatting
- [ ] Add `blurt test` command to test audio/hotkeys

### 3.4 Configuration
- [ ] Add more hotkey options:
  - [ ] Single key hold (e.g., right ctrl only)
  - [ ] Custom combinations
- [ ] Multiple language support structure
- [ ] Model quality selection (small/medium/large)

## Phase 4: Quality & Release

### 4.1 Testing
- [ ] Unit tests for core functionality
- [ ] Integration tests for CLI
- [ ] Test on different distros:
  - [ ] Ubuntu 22.04/24.04
  - [ ] Debian
  - [ ] Fedora (if easy)
- [ ] Test with different audio devices

### 4.2 Documentation
- [ ] Improve README with:
  - [ ] GIF demo
  - [ ] Troubleshooting section
  - [ ] FAQ
- [ ] Man page for `blurt`
- [ ] CONTRIBUTING.md
- [ ] CHANGELOG.md

### 4.3 CI/CD & GitHub Actions
- [ ] Set up GitHub Actions workflows:

#### `.github/workflows/test.yml`
- [ ] Run tests on multiple Python versions
- [ ] Test on Ubuntu 22.04 and 24.04
- [ ] Check code style with ruff/black

#### `.github/workflows/release.yml`
- [ ] Trigger on git tags (v0.1.0, etc.)
- [ ] Build with `uv build`
- [ ] Upload to PyPI with `uv publish` (using GitHub OIDC, no tokens needed)
- [ ] Create GitHub release with changelog

#### Streamlined Release Process
- [ ] Create release script: `scripts/release.sh`
  ```bash
  # Usage: ./scripts/release.sh [major|minor|patch]
  # Auto-bumps version, commits, tags, and pushes
  ```
- [ ] Auto-version bumping:
  - [ ] Reads current version from `blurt/__init__.py`
  - [ ] Bumps semantic version automatically
  - [ ] Updates both `__init__.py` and `pyproject.toml`
- [ ] Ultra-simple release commands:
  ```bash
  ./scripts/release.sh          # Patch: 0.1.0 → 0.1.1
  ./scripts/release.sh minor    # Minor: 0.1.1 → 0.2.0
  ./scripts/release.sh major    # Major: 0.2.0 → 1.0.0
  ```
- [ ] GitHub Actions handles the rest:
  - [ ] Detects new tag
  - [ ] Builds package with `uv build`
  - [ ] Uploads to PyPI with `uv publish`
  - [ ] Creates GitHub release with auto-generated changelog

### 4.4 Release Setup
- [ ] Choose license (MIT suggested)
- [ ] Add LICENSE file
- [ ] Create initial stable release (0.1.0)

#### Release Workflow Example
```bash
# Bug fixes (patch releases)
./scripts/release.sh          # 0.1.0 → 0.1.1
./scripts/release.sh patch    # 0.1.1 → 0.1.2

# New features (minor releases)
./scripts/release.sh minor    # 0.1.2 → 0.2.0

# Breaking changes (major releases)
./scripts/release.sh major    # 0.2.0 → 1.0.0
```

#### Announcement
- [ ] Announce stable releases on:
  - [ ] Reddit (r/linux, r/gnome, r/Python)
  - [ ] Hacker News
  - [ ] Twitter/Mastodon
  - [ ] Python Package Index (automatic)

## Future Ideas (Post-1.0)

- [ ] Wayland support (major effort)
- [ ] System tray icon with menu
- [ ] Voice commands ("new line", "period", etc.)
- [ ] Plugin system for text processing
- [ ] VS Code extension
- [ ] Multiple profiles (coding, writing, etc.)
- [ ] GPU acceleration for larger models
- [ ] Real-time transcription display

## Known Issues to Fix

- [ ] X11 only - no Wayland support
- [ ] PvRecorder device selection issues
- [ ] Hotkey detection in some applications
- [ ] Large model takes long to load

## Development Notes

### Quick Commands
```bash
# Run current version
uv run python -m blurt.main

# Test CLI (after rename)
python -m blurt.cli start

# Development installation
pip install -e .
blurt start

# Build package (modern uv way)
uv build

# Upload to TestPyPI first
UV_PUBLISH_TOKEN=your-test-token uv publish --publish-url https://test.pypi.org/legacy/

# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ blurt

# One-liner releases (automated)
./scripts/release.sh          # Patch bump (default)
./scripts/release.sh minor    # Minor bump
./scripts/release.sh major    # Major bump

# Clean build artifacts
rm -rf build/ dist/ *.egg-info/
```

### Code Style
- Type hints everywhere
- Docstrings for public functions
- Keep it simple - no over-engineering
- User-friendly error messages
- Fail gracefully

---

**Current Priority:** Phase 3 - Python packaging to achieve `pip install blurt` experience.

**Completed:**
- ✅ Phase 1: Code quality tooling and testing framework
- ✅ Phase 2: CLI daemon management and process handling
- 🚀 **Current:** Phase 3: Python packaging and PyPI distribution
