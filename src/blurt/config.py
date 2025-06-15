"""Configuration management for blurt."""

import os
from pathlib import Path
from typing import Dict, Any

import tomli_w


class Config:
    """Configuration manager following XDG Base Directory standards."""
    
    def __init__(self) -> None:
        # XDG Base Directory paths
        self.config_dir = self._get_xdg_config_dir()
        self.data_dir = self._get_xdg_data_dir() 
        self.cache_dir = self._get_xdg_cache_dir()
        self.state_dir = self._get_xdg_state_dir()
        
        # Specific paths
        self.config_file = self.config_dir / 'config.toml'
        self.models_dir = self.data_dir / 'models'
        self.log_file = self.state_dir / 'blurt.log'
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            import tomllib
            with open(self.config_file, 'rb') as f:
                return tomllib.load(f)
        else:
            return self._create_default_config()
    
    def _get_xdg_config_dir(self) -> Path:
        """Get XDG config directory."""
        return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'blurt'
    
    def _get_xdg_data_dir(self) -> Path:
        """Get XDG data directory."""
        return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'blurt'
    
    def _get_xdg_cache_dir(self) -> Path:
        """Get XDG cache directory."""
        return Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'blurt'
    
    def _get_xdg_state_dir(self) -> Path:
        """Get XDG state directory."""
        return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local' / 'state')) / 'blurt'
    
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
                'name': 'vosk-model-small-en-us-0.15',
                'data_dir': str(self.data_dir),
                'cache_dir': str(self.cache_dir),
            },
            'daemon': {
                'log_file': str(self.log_file),
                'log_level': 'info',
            },
            'output': {
                'typing_delay': 0.01,
            }
        }
        
        # Create all necessary directories
        for directory in [self.config_dir, self.data_dir, self.cache_dir, self.state_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create config file
        with open(self.config_file, 'wb') as f:
            tomli_w.dump(config, f)
        
        print(f"Created default config at: {self.config_file}")
        print(f"Data directory: {self.data_dir}")
        print(f"Cache directory: {self.cache_dir}")
        print(f"State directory: {self.state_dir}")
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
    def model_path(self) -> Path:
        """Full path to the Vosk model directory."""
        model_name = self._config['model']['name']
        return self.models_dir / model_name
    
    @property
    def log_file_path(self) -> Path:
        """Path to the log file."""
        return Path(self._config['daemon']['log_file'])
    
    @property 
    def log_level(self) -> str:
        """Logging level."""
        return self._config['daemon']['log_level']
    
    @property
    def typing_delay(self) -> float:
        """Delay between typed characters."""
        return self._config['output']['typing_delay']