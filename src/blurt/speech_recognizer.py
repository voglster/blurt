"""Speech recognition using Vosk."""

import json
import wave
import io
from pathlib import Path
from typing import Optional

import vosk

from .config import Config


class SpeechRecognizer:
    """Speech recognizer using Vosk."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self.model: Optional[vosk.Model] = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the Vosk model."""
        model_path = Path(self.config.model_path)
        
        if not model_path.exists():
            print(f"Model not found at {model_path}")
            print("Downloading lightweight English model...")
            self._download_model()
        
        try:
            self.model = vosk.Model(str(model_path))
            print(f"Loaded Vosk model from {model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
    
    def _download_model(self) -> None:
        """Download the Vosk model."""
        import urllib.request
        import zipfile
        import tempfile
        
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        model_path = Path(self.config.model_path)
        
        # Create models directory
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        print("Downloading Vosk model (this may take a few minutes)...")
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            urllib.request.urlretrieve(model_url, tmp_file.name)
            
            # Extract the model
            with zipfile.ZipFile(tmp_file.name, 'r') as zip_ref:
                zip_ref.extractall(model_path.parent)
        
        print(f"Model downloaded and extracted to {model_path}")
    
    def recognize(self, audio_data: bytes) -> str:
        """Recognize speech from audio data."""
        if not self.model:
            return ""
        
        # Create recognizer
        rec = vosk.KaldiRecognizer(self.model, self.config.sample_rate)
        
        # Process audio data
        with io.BytesIO(audio_data) as audio_buffer:
            with wave.open(audio_buffer, 'rb') as wav_file:
                while True:
                    data = wav_file.readframes(4096)
                    if len(data) == 0:
                        break
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if result.get('text'):
                            return result['text'].strip()
                
                # Get final result
                final_result = json.loads(rec.FinalResult())
                return final_result.get('text', '').strip()