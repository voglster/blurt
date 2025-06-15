"""Tests for configuration management."""

import tempfile
from pathlib import Path

import pytest

from src.blurt.config import Config


def test_config_creation():
    """Test that config can be created."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock XDG directories
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        
        try:
            config = Config()
            assert config.sample_rate == 16000
            assert config.channels == 1
            assert config.typing_delay == 0.01
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_xdg_paths():
    """Test XDG directory path generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        
        try:
            config = Config()
            
            # Check paths are under temp directory
            assert str(config.config_dir).startswith(temp_dir)
            assert str(config.data_dir).startswith(temp_dir)
            assert str(config.cache_dir).startswith(temp_dir)
            assert str(config.state_dir).startswith(temp_dir)
            
            # Check directory structure
            assert config.config_dir.name == "blurt"
            assert "config" in str(config.config_dir)
            assert "share" in str(config.data_dir)
            assert "cache" in str(config.cache_dir)
            assert "state" in str(config.state_dir)
            
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_model_path():
    """Test model path generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        
        try:
            config = Config()
            model_path = config.model_path
            
            assert "vosk-model-small-en-us-0.15" in str(model_path)
            assert model_path.parent == config.models_dir
            
        finally:
            if old_home:
                os.environ["HOME"] = old_home