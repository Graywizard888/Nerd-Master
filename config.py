import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class BotConfig:
    """Configuration for Nerd Master Bot"""
    
    # Bot Settings
    BOT_NAME: str = "Nerd Master"
    BOT_USERNAME: str = "NerdMasterBot"
    COMMAND_PREFIX: str = "/Nerd"
    
    # Creator Info
    CREATOR_NAME: str = "Graywizard"
    GROUP_NAME: str = "Graywizard Projects"
    
    # Projects
    PROJECTS: dict = None
    
    # API Keys
    TELEGRAM_BOT_TOKEN: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # Default AI Settings
    DEFAULT_AI_PROVIDER: str = "gemini"
    DEFAULT_OPENAI_MODEL: str = "gpt-4o"
    DEFAULT_GEMINI_MODEL: str = "gemini-1.5-pro"
    
    # Available Models
    OPENAI_MODELS: list = None
    GEMINI_MODELS: list = None
    
    # Database
    DATABASE_URL: str = ""
    
    def __post_init__(self):
        # Load from environment
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///nerd_master.db")
        
        # Projects
        self.PROJECTS = {
            "Enhancify": {
                "url": "https://github.com/Graywizard888/Enhancify",
                "description": "A powerful enhancement tool for Android apps"
            },
            "Terminal Ex": {
                "url": "https://github.com/Graywizard888/Terminal_EX",
                "description": "Extended terminal with advanced features"
            },
            "Custom-Enhancify-aapt2-binary": {
                "url": "https://github.com/Graywizard888/Custom-Enhancify-aapt2-binary",
                "description": "Custom aapt2 binary for Enhancify"
            }
        }
        
        # OpenAI Models
        self.OPENAI_MODELS = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "o1-preview",
            "o1-mini",
            "gpt-5.1-high",
            "gpt-5.1",
            "gpt-5-chat",
        ]
        
        # Gemini Models
        self.GEMINI_MODELS = [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.0-pro",
            "gemini-2.0-flash-exp"
            "gemini-3-pro"
            "gemini-2.5-pro"
            "gemini-2.5-flash"
        ]

config = BotConfig()
