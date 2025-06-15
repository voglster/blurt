"""Configuration management for tab_voice."""

import os
from pathlib import Path
from typing import Dict, Any

import tomli_w


class Config:
    """Configuration manager."""
    
    def __init__(self) -> None:
        self.config_dir = Path.home() / '.config' / 'tab_voice'
        self.config_file = self.config_dir / 'config.toml'
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            import tomllib
            with open(self.config_file, 'rb') as f:
                return tomllib.load(f)
        else:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration."""
        config = {
            'audio': {
                'sample_rate': 16000,
                'hold_threshold_ms': 400,
                'post_release_ms': 300,
                'channels': 1,
            },
            'model': {
                'path': 'models/vosk-model-small-en-us-0.15',
            },
            'output': {
                'typing_delay': 0.01,
            }
        }
        
        # Create config directory and file
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'wb') as f:
            tomli_w.dump(config, f)
        
        print(f"Created default config at: {self.config_file}")
        return config
    
    @property
    def sample_rate(self) -> int:
        """Audio sample rate."""
        return self._config['audio']['sample_rate']
    
    @property
    def hold_threshold_ms(self) -> int:
        """Tab hold threshold in milliseconds."""
        return self._config['audio']['hold_threshold_ms']
    
    @property
    def post_release_ms(self) -> int:
        """Post-release recording time in milliseconds."""
        return self._config['audio']['post_release_ms']
    
    @property
    def channels(self) -> int:
        """Audio channels."""
        return self._config['audio']['channels']
    
    @property
    def model_path(self) -> str:
        """Vosk model path."""
        return self._config['model']['path']
    
    @property
    def typing_delay(self) -> float:
        """Delay between typed characters."""
        return self._config['output']['typing_delay']