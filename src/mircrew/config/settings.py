"""Configuration management for MirCrew Indexer"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MirCrewConfig:
    """Central configuration class"""
    username: str
    password: str
    base_url: str = "https://mircrew-releases.org"
    api_host: str = "0.0.0.0"
    api_port: int = 9118
    timeout: int = 30
    max_results: int = 100

    @classmethod
    def from_env(cls) -> 'MirCrewConfig':
        """Load configuration from environment variables"""
        username = os.getenv('MIRCREW_USERNAME')
        password = os.getenv('MIRCREW_PASSWORD')

        if not username or not password:
            raise ValueError("MIRCREW_USERNAME and MIRCREW_PASSWORD must be set")

        return cls(
            username=username,
            password=password,
            api_host=os.getenv('API_HOST', '0.0.0.0'),
            api_port=int(os.getenv('API_PORT', 9118)),
            timeout=int(os.getenv('TIMEOUT', 30)),
            max_results=int(os.getenv('MAX_RESULTS', 100))
        )