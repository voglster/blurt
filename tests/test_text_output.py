"""Tests for text output functionality."""

import tempfile
from unittest.mock import Mock, patch

from src.blurt.config import Config
from src.blurt.text_output import TextOutput


def test_text_output_creation():
    """Test that TextOutput can be created."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        
        try:
            config = Config()
            with patch("src.blurt.text_output.Controller"):
                text_output = TextOutput(config)
                assert text_output.config == config
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_empty_text_handling():
    """Test that empty text is handled correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        
        try:
            config = Config()
            with patch("src.blurt.text_output.Controller") as mock_controller:
                mock_keyboard = Mock()
                mock_controller.return_value = mock_keyboard
                
                text_output = TextOutput(config)
                text_output.type_text("")  # Empty string
                text_output.type_text("   ")  # Whitespace only
                
                # Should not call keyboard.type for empty strings
                mock_keyboard.type.assert_not_called()
                
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_text_typing():
    """Test that text is typed correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        
        try:
            config = Config()
            with patch("src.blurt.text_output.Controller") as mock_controller:
                mock_keyboard = Mock()
                mock_controller.return_value = mock_keyboard
                
                text_output = TextOutput(config)
                text_output.type_text("hello")
                
                # Should call keyboard.type for each character
                assert mock_keyboard.type.call_count == 5
                
        finally:
            if old_home:
                os.environ["HOME"] = old_home