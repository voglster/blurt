# Blurt Development TODO

## Phase 1: Code Quality & Development Tools (PRIORITY)

> **🚨 STOP: No new features until code quality is established!**
>
> We need a solid foundation before continuing development. Quality first!

## Phase 1.1: Code Quality & Development Tools (IMMEDIATE)

### 1.1.1 Code Formatting & Linting
- [ ] Add `ruff` for fast Python linting and formatting
  - [ ] Configure `ruff.toml` or `pyproject.toml` rules
  - [ ] Run `ruff check` and `ruff format` on codebase
  - [ ] Fix all linting issues
- [ ] Set up `pre-commit` hooks
  - [ ] Install pre-commit framework
  - [ ] Configure `.pre-commit-config.yaml`
  - [ ] Include ruff, type checking, and other quality checks
  - [ ] Test pre-commit hooks work locally

### 1.1.2 Type Checking & Testing
- [ ] Add comprehensive type hints throughout codebase
  - [ ] Use `mypy` for static type checking
  - [ ] Configure `mypy.ini` or `pyproject.toml` settings
  - [ ] Fix all type errors
- [ ] Set up testing framework
  - [ ] Choose testing framework (pytest recommended)
  - [ ] Write unit tests for core functionality
  - [ ] Add integration tests for CLI commands
  - [ ] Set up test coverage with `coverage.py`
  - [ ] Aim for >80% code coverage

### 1.1.3 Dead Code & Security
- [ ] Use `vulture` to find dead/unused code
  - [ ] Remove unused imports and functions
  - [ ] Clean up any legacy code from tab_voice era
- [ ] Security scanning
  - [ ] Use `bandit` for security issue detection
  - [ ] Fix any security warnings
  - [ ] Review dependencies for known vulnerabilities

### 1.1.4 Documentation & Code Quality
- [ ] Add comprehensive docstrings
  - [ ] All public functions and classes
  - [ ] Follow Google or NumPy docstring style
  - [ ] Use `pydocstyle` to enforce consistency
- [ ] Code complexity analysis
  - [ ] Use `radon` to check cyclomatic complexity
  - [ ] Refactor overly complex functions
- [ ] Import organization
  - [ ] Use `isort` to organize imports consistently
  - [ ] Configure to work with ruff

### 1.1.5 Development Workflow
- [ ] Create development scripts
  - [ ] `scripts/lint.sh` - Run all linting tools
  - [ ] `scripts/test.sh` - Run all tests with coverage
  - [ ] `scripts/check.sh` - Full quality check before commit
- [ ] Update `pyproject.toml` with dev dependencies:
  ```toml
  [project.optional-dependencies]
  dev = [
      "ruff>=0.1.0",
      "mypy>=1.0.0",
      "pytest>=7.0.0",
      "coverage[toml]>=7.0.0",
      "vulture>=2.0.0",
      "bandit>=1.7.0",
      "pre-commit>=3.0.0",
      "pydocstyle>=6.0.0",
      "radon>=6.0.0",
      "isort>=5.0.0",
  ]
  ```

### 1.1.6 CI/CD Quality Gates
- [ ] GitHub Actions workflow for quality checks
  - [ ] Run ruff, mypy, tests on every PR
  - [ ] Block merges if quality checks fail
  - [ ] Generate coverage reports
- [ ] Add quality badges to README
  - [ ] Build status, coverage %, PyPI version
  - [ ] Code quality score if using external service

### 1.1.7 Configuration Files to Add
- [ ] `.pre-commit-config.yaml`
- [ ] `mypy.ini` or mypy config in `pyproject.toml`
- [ ] `ruff.toml` or ruff config in `pyproject.toml`
- [ ] `.github/workflows/quality.yml`
- [ ] Update `.gitignore` for development artifacts

## Phase 2: CLI & Process Management (After Quality)

### 2.1 Basic CLI Structure ✅
- [x] Create `cli.py` with start/stop/restart/status/install commands
- [x] Basic PID file management

### 2.2 Daemon Mode 🔄
- [ ] Implement proper daemon process
  - [ ] Fork process and detach from terminal
  - [ ] Redirect stdout/stderr to log file
  - [ ] Handle signals properly (SIGTERM, SIGINT)
- [ ] Log file in `~/.local/state/blurt/blurt.log`
- [ ] Rotate logs when they get too big
- [ ] Add `--foreground` flag for debugging

### 2.3 Process Management
- [ ] Improve PID file handling
  - [ ] Lock file to prevent multiple instances
  - [ ] Check if PID actually belongs to blurt
- [ ] Better error messages
  - [ ] "Already running" with instructions
  - [ ] "Not running" with helpful next steps
  - [ ] Permission errors with solutions
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

## Phase 3: Installation & Packaging

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

Priority: Focus on Phase 1 & 2 first to get a working `pip install blurt` experience.
