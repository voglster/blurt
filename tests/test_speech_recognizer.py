"""Tests for speech recognition functionality."""

import json
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.blurt.config import Config
from src.blurt.speech_recognizer import SpeechRecognizer


@pytest.fixture
def temp_home():
    """Provide temporary home directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir

        try:
            yield temp_dir
        finally:
            if old_home:
                os.environ["HOME"] = old_home


@pytest.fixture
def mock_config(temp_home):
    """Provide mocked config with temporary directories."""
    config = Config()
    # Create model directory structure
    config.models_dir.mkdir(parents=True, exist_ok=True)
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    return config


def test_speech_recognizer_initialization_with_existing_model(mock_config):
    """Test SpeechRecognizer initializes when model exists."""
    # Create fake model directory
    mock_config.model_path.mkdir(parents=True, exist_ok=True)

    with patch("vosk.Model") as mock_model:
        mock_model_instance = Mock()
        mock_model.return_value = mock_model_instance

        recognizer = SpeechRecognizer(mock_config)

        assert recognizer.config == mock_config
        assert recognizer.model == mock_model_instance
        mock_model.assert_called_once_with(str(mock_config.model_path))


def test_speech_recognizer_initialization_model_missing_triggers_download(mock_config):
    """Test SpeechRecognizer downloads model when missing."""
    # Model path doesn't exist
    assert not mock_config.model_path.exists()

    with (
        patch("vosk.Model") as mock_model,
        patch.object(SpeechRecognizer, "_download_model") as mock_download,
    ):
        mock_model_instance = Mock()
        mock_model.return_value = mock_model_instance

        SpeechRecognizer(mock_config)

        mock_download.assert_called_once()
        mock_model.assert_called_once_with(str(mock_config.model_path))


def test_load_model_success(mock_config):
    """Test _load_model succeeds with existing model."""
    mock_config.model_path.mkdir(parents=True, exist_ok=True)

    with patch("vosk.Model") as mock_model:
        mock_model_instance = Mock()
        mock_model.return_value = mock_model_instance

        recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
        recognizer.config = mock_config
        recognizer.model = None

        recognizer._load_model()

        assert recognizer.model == mock_model_instance


def test_load_model_failure_raises_exception(mock_config):
    """Test _load_model raises exception on Vosk model failure."""
    mock_config.model_path.mkdir(parents=True, exist_ok=True)

    with patch("vosk.Model", side_effect=RuntimeError("Model load failed")):
        recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
        recognizer.config = mock_config
        recognizer.model = None

        with pytest.raises(RuntimeError, match="Model load failed"):
            recognizer._load_model()


@patch("urllib.request.urlretrieve")
@patch("zipfile.ZipFile")
@patch("os.unlink")
def test_download_model_success(mock_unlink, mock_zipfile, mock_urlretrieve, mock_config):
    """Test _download_model successfully downloads and extracts model."""
    # Mock zipfile extraction
    mock_zip_instance = Mock()
    mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config

    recognizer._download_model()

    # Verify download
    expected_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    expected_zip_path = mock_config.cache_dir / "vosk-model.zip"
    mock_urlretrieve.assert_called_once_with(expected_url, expected_zip_path)

    # Verify extraction
    mock_zipfile.assert_called_once_with(expected_zip_path, "r")
    mock_zip_instance.extractall.assert_called_once_with(mock_config.models_dir)

    # Verify cleanup
    mock_unlink.assert_called_once_with(expected_zip_path)


@patch("urllib.request.urlretrieve", side_effect=Exception("Download failed"))
def test_download_model_failure(mock_urlretrieve, mock_config):
    """Test _download_model handles download failure."""
    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config

    with pytest.raises(Exception, match="Download failed"):
        recognizer._download_model()


def test_recognize_no_model_returns_empty_string(mock_config):
    """Test recognize returns empty string when no model loaded."""
    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = None

    result = recognizer.recognize(b"fake audio data")

    assert result == ""


@patch("vosk.KaldiRecognizer")
@patch("wave.open")
def test_recognize_with_successful_recognition(mock_wave_open, mock_recognizer_class, mock_config):
    """Test recognize successfully processes audio and returns text."""
    # Setup mocks
    mock_model = Mock()
    mock_recognizer = Mock()
    mock_recognizer_class.return_value = mock_recognizer

    # Mock wave file
    mock_wav_file = Mock()
    mock_wav_file.readframes.side_effect = [b"audio_chunk", b""]  # First chunk, then EOF
    mock_wave_open.return_value.__enter__.return_value = mock_wav_file

    # Mock recognition results
    mock_recognizer.AcceptWaveform.return_value = True
    mock_recognizer.Result.return_value = json.dumps({"text": "hello world"})

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = mock_model

    result = recognizer.recognize(b"fake audio wav data")

    assert result == "hello world"
    mock_recognizer_class.assert_called_once_with(mock_model, mock_config.sample_rate)
    mock_recognizer.AcceptWaveform.assert_called_once_with(b"audio_chunk")


@patch("vosk.KaldiRecognizer")
@patch("wave.open")
def test_recognize_with_final_result_only(mock_wave_open, mock_recognizer_class, mock_config):
    """Test recognize uses final result when no intermediate results."""
    # Setup mocks
    mock_model = Mock()
    mock_recognizer = Mock()
    mock_recognizer_class.return_value = mock_recognizer

    # Mock wave file
    mock_wav_file = Mock()
    mock_wav_file.readframes.side_effect = [b"audio_chunk", b""]  # First chunk, then EOF
    mock_wave_open.return_value.__enter__.return_value = mock_wav_file

    # Mock recognition - no intermediate results, only final
    mock_recognizer.AcceptWaveform.return_value = False
    mock_recognizer.FinalResult.return_value = json.dumps({"text": "final result"})

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = mock_model

    result = recognizer.recognize(b"fake audio wav data")

    assert result == "final result"
    mock_recognizer.FinalResult.assert_called_once()


@patch("vosk.KaldiRecognizer")
@patch("wave.open")
def test_recognize_with_empty_result(mock_wave_open, mock_recognizer_class, mock_config):
    """Test recognize handles empty recognition results."""
    # Setup mocks
    mock_model = Mock()
    mock_recognizer = Mock()
    mock_recognizer_class.return_value = mock_recognizer

    # Mock wave file
    mock_wav_file = Mock()
    mock_wav_file.readframes.side_effect = [b"audio_chunk", b""]
    mock_wave_open.return_value.__enter__.return_value = mock_wav_file

    # Mock empty recognition results
    mock_recognizer.AcceptWaveform.return_value = False
    mock_recognizer.FinalResult.return_value = json.dumps({"text": ""})

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = mock_model

    result = recognizer.recognize(b"fake audio wav data")

    assert result == ""


@patch("vosk.KaldiRecognizer")
@patch("wave.open")
def test_recognize_with_no_text_in_result(mock_wave_open, mock_recognizer_class, mock_config):
    """Test recognize handles results without text field."""
    # Setup mocks
    mock_model = Mock()
    mock_recognizer = Mock()
    mock_recognizer_class.return_value = mock_recognizer

    # Mock wave file
    mock_wav_file = Mock()
    mock_wav_file.readframes.side_effect = [b"audio_chunk", b""]
    mock_wave_open.return_value.__enter__.return_value = mock_wav_file

    # Mock result without text field
    mock_recognizer.AcceptWaveform.return_value = False
    mock_recognizer.FinalResult.return_value = json.dumps({"confidence": 0.95})

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = mock_model

    result = recognizer.recognize(b"fake audio wav data")

    assert result == ""


@patch("vosk.KaldiRecognizer")
@patch("wave.open")
def test_recognize_with_whitespace_stripping(mock_wave_open, mock_recognizer_class, mock_config):
    """Test recognize strips whitespace from results."""
    # Setup mocks
    mock_model = Mock()
    mock_recognizer = Mock()
    mock_recognizer_class.return_value = mock_recognizer

    # Mock wave file
    mock_wav_file = Mock()
    mock_wav_file.readframes.side_effect = [b"audio_chunk", b""]
    mock_wave_open.return_value.__enter__.return_value = mock_wav_file

    # Mock result with whitespace
    mock_recognizer.AcceptWaveform.return_value = True
    mock_recognizer.Result.return_value = json.dumps({"text": "  hello world  "})

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = mock_model

    result = recognizer.recognize(b"fake audio wav data")

    assert result == "hello world"


@patch("vosk.KaldiRecognizer")
@patch("wave.open")
def test_recognize_multiple_audio_chunks(mock_wave_open, mock_recognizer_class, mock_config):
    """Test recognize processes multiple audio chunks."""
    # Setup mocks
    mock_model = Mock()
    mock_recognizer = Mock()
    mock_recognizer_class.return_value = mock_recognizer

    # Mock wave file with multiple chunks
    mock_wav_file = Mock()
    mock_wav_file.readframes.side_effect = [
        b"chunk1",
        b"chunk2",
        b"chunk3",
        b"",  # Multiple chunks then EOF
    ]
    mock_wave_open.return_value.__enter__.return_value = mock_wav_file

    # Mock - first two calls return False, third returns True with result
    mock_recognizer.AcceptWaveform.side_effect = [False, False, True]
    mock_recognizer.Result.return_value = json.dumps({"text": "multiple chunks"})

    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = mock_config
    recognizer.model = mock_model

    result = recognizer.recognize(b"fake multi-chunk wav data")

    assert result == "multiple chunks"
    assert mock_recognizer.AcceptWaveform.call_count == 3
