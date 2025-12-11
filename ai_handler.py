import asyncio
import logging
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)

class AIHandler:
    """Handles AI API calls for OpenAI and Gemini"""
    
    def __init__(self):
        self.openai_client = None
        self.openai_module = None
        self.genai_module = None
        self.gemini_models = {}
        self._openai_initialized = False
        self._gemini_initialized = False
        logger.info("AIHandler created - clients will be initialized on first use")
    
    def _setup_openai(self) -> bool:
        """Setup OpenAI client lazily"""
        if self._openai_initialized:
            return self.openai_client is not None
        
        self._openai_initialized = True
        
        if not config.has_openai():
            logger.warning("OpenAI API key not configured")
            return False
        
        try:
            import openai
            self.openai_module = openai
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            return False
    
    def _setup_gemini(self) -> bool:
        """Setup Gemini client lazily"""
        if self._gemini_initialized:
            return self.genai_module is not None
        
        self._gemini_initialized = True
        
        if not config.has_gemini():
            logger.warning("Gemini API key not configured")
            return False
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.genai_module = genai
            logger.info("Gemini client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            return False
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for the AI"""
        projects_info = "\n".join([
            f"- **{name}**: {info['description']} - {info['url']}"
            for name, info in config.PROJECTS.items()
        ])
        
        return f"""You are **{config.BOT_NAME}**, an advanced AI assistant created by **{config.CREATOR_NAME}** for the **{config.GROUP_NAME}** Telegram group.

## Your Identity:
- Name: {config.BOT_NAME}
- Creator: {config.CREATOR_NAME}
- Purpose: Assist users with questions, coding, projects, and general knowledge

## Creator's Projects:
{projects_info}

## Your Capabilities:
- Answer questions on programming, technology, and general topics
- Help with code debugging, writing, and optimization
- Provide information about {config.CREATOR_NAME}'s projects
- Assist with Android development, terminal operations, and app enhancement
- Engage in natural conversations

## Guidelines:
- Be helpful, friendly, and professional
- Provide accurate and detailed responses
- Format code with proper syntax highlighting using markdown
- When asked about projects, provide relevant GitHub links
- Acknowledge when you don't know something
- Use emojis sparingly to make responses engaging

## Response Format:
- Use markdown formatting for better readability
- Use code blocks with language specification for code
- Keep responses concise but comprehensive
- Break down complex explanations into steps"""

    async def generate_openai_response(
        self, 
        prompt: str, 
        model: str = None,
        chat_history: List[Dict[str, str]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate response using OpenAI API"""
        
        # Try to setup OpenAI if not already done
        if not self._setup_openai():
            return {
                "success": False,
                "error": "OpenAI API key not configured or invalid",
                "response": None
            }
        
        model = model or config.DEFAULT_OPENAI_MODEL
        
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        if chat_history:
            messages.extend(chat_history[-10:])  # Last 10 messages for context
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            # Handle O1 models differently (they don't support system messages)
            if model.startswith("o1"):
                messages = [{"role": "user", "content": f"{self.get_system_prompt()}\n\n{prompt}"}]
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages
                )
            else:
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            
            return {
                "success": True,
                "response": response.choices[0].message.content,
                "model": model,
                "provider": "openai",
                "tokens": response.usage.total_tokens if response.usage else 0
            }
            
        except self.openai_module.RateLimitError:
            return {
                "success": False,
                "error": "Rate limit exceeded. Please try again later.",
                "response": None
            }
        except self.openai_module.AuthenticationError:
            return {
                "success": False,
                "error": "Invalid OpenAI API key.",
                "response": None
            }
        except self.openai_module.APIError as e:
            return {
                "success": False,
                "error": f"OpenAI API error: {str(e)}",
                "response": None
            }
        except Exception as e:
            logger.error(f"OpenAI unexpected error: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "response": None
            }
    
    async def generate_gemini_response(
        self,
        prompt: str,
        model: str = None,
        chat_history: List[Dict[str, str]] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate response using Gemini API"""
        
        # Try to setup Gemini if not already done
        if not self._setup_gemini():
            return {
                "success": False,
                "error": "Gemini API key not configured or invalid",
                "response": None
            }
        
        model_name = model or config.DEFAULT_GEMINI_MODEL
        
        try:
            # Get or create model instance
            if model_name not in self.gemini_models:
                generation_config = self.genai_module.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature
                )
                self.gemini_models[model_name] = self.genai_module.GenerativeModel(
                    model_name,
                    generation_config=generation_config,
                    system_instruction=self.get_system_prompt()
                )
            
            gemini_model = self.gemini_models[model_name]
            
            # Build conversation history for Gemini
            history = []
            if chat_history:
                for msg in chat_history[-10:]:
                    role = "user" if msg["role"] == "user" else "model"
                    history.append({"role": role, "parts": [msg["content"]]})
            
            # Create chat session and send message
            chat = gemini_model.start_chat(history=history)
            response = await asyncio.to_thread(chat.send_message, prompt)
            
            return {
                "success": True,
                "response": response.text,
                "model": model_name,
                "provider": "gemini",
                "tokens": 0  # Gemini doesn't always return token count
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini error: {error_msg}")
            
            if "API_KEY_INVALID" in error_msg or "INVALID_ARGUMENT" in error_msg:
                return {
                    "success": False,
                    "error": "Invalid Gemini API key or model not available.",
                    "response": None
                }
            if "quota" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Gemini API quota exceeded. Please try again later.",
                    "response": None
                }
            return {
                "success": False,
                "error": f"Gemini API error: {error_msg}",
                "response": None
            }
    
    async def generate_response(
        self,
        prompt: str,
        provider: str = None,
        model: str = None,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Generate response using specified provider"""
        
        provider = (provider or config.DEFAULT_AI_PROVIDER).lower()
        
        if provider in ["openai", "chatgpt"]:
            return await self.generate_openai_response(prompt, model, chat_history)
        elif provider == "gemini":
            return await self.generate_gemini_response(prompt, model, chat_history)
        else:
            return {
                "success": False,
                "error": f"Unknown provider: {provider}",
                "response": None
            }

# Global AI handler instance
ai_handler = AIHandler()
