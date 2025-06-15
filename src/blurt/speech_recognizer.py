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
        model_path = self.config.model_path
        
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
        import os
        
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        model_path = self.config.model_path
        
        # Create models directory
        self.config.models_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading Vosk model to {self.config.models_dir}...")
        print("This may take a few minutes...")
        
        # Download to cache directory first
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.config.cache_dir / "vosk-model.zip"
        
        urllib.request.urlretrieve(model_url, zip_path)
        
        # Extract the model to data directory
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.config.models_dir)
        
        # Clean up zip file
        os.unlink(zip_path)
        
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