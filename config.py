import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List

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
    PROJECTS: Dict = field(default_factory=dict)
    
    # API Keys
    TELEGRAM_BOT_TOKEN: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # Default AI Settings
    DEFAULT_AI_PROVIDER: str = "gemini"
    DEFAULT_OPENAI_MODEL: str = "gpt-4o"
    DEFAULT_GEMINI_MODEL: str = "gemini-1.5-pro"
    
    # Available Models
    OPENAI_MODELS: List = field(default_factory=list)
    GEMINI_MODELS: List = field(default_factory=list)
    
    # Database
    DATABASE_URL: str = ""
    
    def __post_init__(self):
        # Load from environment
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///nerd_master.db")
        
        # Projects
        self.PROJECTS = {
            "Enhancify": {
                "url": "https://github.com/Graywizard888/Enhancify",
                "description": "A Ultimate Patcher tool for Android apps"
            },
            "Terminal Ex": {
                "url": "https://github.com/Graywizard888/Terminal_EX",
                "description": "Termux-Monet Fork with Extended Android versions support"
            },
            "Custom-Enhancify-aapt2-binary": {
                "url": "https://github.com/Graywizard888/Custom-Enhancify-aapt2-binary",
                "description": "Custom aapt2 binary Specially for Enhancify"
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
            "o1-mini"
        ]
        
        # Gemini Models
        self.GEMINI_MODELS = [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.0-pro",
            "gemini-2.0-flash-exp"
        ]
    
    def has_openai(self) -> bool:
        """Check if OpenAI API key is configured"""
        return bool(self.OPENAI_API_KEY and len(self.OPENAI_API_KEY) > 10)
    
    def has_gemini(self) -> bool:
        """Check if Gemini API key is configured"""
        return bool(self.GEMINI_API_KEY and len(self.GEMINI_API_KEY) > 10)
    
    def has_any_ai(self) -> bool:
        """Check if any AI API key is configured"""
        return self.has_openai() or self.has_gemini()

config = BotConfig()
