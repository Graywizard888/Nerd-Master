import os
import logging
import asyncio
from typing import Optional
from datetime import datetime
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode, ChatType

from config import config
from database import db
from ai_handler import ai_handler
from group_operations import group_ops

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def get_user_mention(user) -> str:
    """Get user mention"""
    if user.username:
        return f"@{user.username}"
    return f"[{user.first_name}](tg://user?id={user.id})"

def parse_duration(duration_str: str) -> Optional[int]:
    """Parse duration string to seconds"""
    match = re.match(r'^(\d+)([smhd])$', duration_str.lower())
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return value * multipliers[unit]

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get target user from reply or arguments"""
    # Check if replying to a message
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    
    # Check arguments
    if context.args:
        arg = context.args[0]
        # Handle @username
        if arg.startswith('@'):
            # Note: Cannot get user ID from username without prior interaction
            return None
        # Handle user ID
        try:
            user_id = int(arg)
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            return member.user
        except:
            return None
    
    return None

# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Save user settings
    db.set_user_settings(user.id, user.username or user.first_name)
    
    welcome_text = f"""
🤖 **Welcome to {config.BOT_NAME}!**

I'm an advanced AI assistant created by **{config.CREATOR_NAME}** for the **{config.GROUP_NAME}** community.

**🔧 My Capabilities:**
• AI-powered conversations (GPT-4o, Gemini 1.5 Pro)
• Code assistance and debugging
• Group administration
• Information about creator's projects

**📚 Commands:**
• `/Nerd <question>` - Ask me anything
• `/help` - Show all commands
• `/projects` - View creator's projects
• `/models` - Switch AI models
• `/settings` - View your settings

**💡 Tip:** You can also reply to my messages to continue the conversation!

Created with ❤️ by **{config.CREATOR_NAME}**
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📚 Projects", callback_data="projects"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("🤖 Models", callback_data="models"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = f"""
📖 **{config.BOT_NAME} Help**

**🤖 AI Commands:**
• `/Nerd <question>` - Ask me anything
• `/ask <question>` - Alternative to /Nerd
• `/models` - View and switch AI models
• `/provider <openai|gemini>` - Switch AI provider
• `/clear` - Clear chat history

**📁 Project Commands:**
• `/projects` - View all projects
• `/enhancify` - Info about Enhancify
• `/terminalex` - Info about Terminal Ex
• `/aapt2` - Info about Custom aapt2

**⚙️ Settings Commands:**
• `/settings` - View your settings
• `/mystats` - View your usage stats

**👑 Admin Commands (Groups Only):**
• `/ban` - Ban a user (reply or mention)
• `/unban` - Unban a user
• `/kick` - Kick a user
• `/mute [duration]` - Mute a user
• `/unmute` - Unmute a user
• `/promote` - Promote to admin
• `/demote` - Demote from admin
• `/pin` - Pin a message
• `/unpin` - Unpin messages
• `/chatinfo` - Get chat information
• `/setwelcome <message>` - Set welcome message
• `/toggleai` - Enable/disable AI in group

**💡 Tips:**
• Reply to my messages to continue conversation
• Use `/Nerd` in groups to call me
• Admins can configure group-specific settings
"""
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def nerd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /Nerd command - Main AI query"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Get the question
    if context.args:
        question = ' '.join(context.args)
    elif update.message.reply_to_message and update.message.reply_to_message.text:
        question = update.message.reply_to_message.text
    else:
        await update.message.reply_text(
            "❓ Please provide a question!\n\nUsage: `/Nerd <your question>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Get user/group settings
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        settings = db.get_group_settings(chat.id) or {}
    else:
        settings = db.get_user_settings(user.id) or {}
    
    provider = settings.get('ai_provider', config.DEFAULT_AI_PROVIDER)
    model = settings.get(f'{provider}_model', 
                         config.DEFAULT_OPENAI_MODEL if provider == 'openai' else config.DEFAULT_GEMINI_MODEL)
    
    # Show typing indicator
    await context.bot.send_chat_action(chat.id, "typing")
    
    # Get chat history for context
    chat_history = db.get_chat_history(chat.id, limit=10)
    
    # Generate response
    result = await ai_handler.generate_response(
        prompt=question,
        provider=provider,
        model=model,
        chat_history=chat_history
    )
    
    if result['success']:
        response_text = result['response']
        
        # Save to chat history
        db.add_chat_history(user.id, chat.id, update.message.message_id, 
                           'user', question, provider, model)
        
        # Add model info footer
        footer = f"\n\n_🤖 {result['model']} | {result['provider'].upper()}_"
        
        # Try to send with markdown, fallback to plain text
        try:
            sent_message = await update.message.reply_text(
                response_text + footer,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            sent_message = await update.message.reply_text(response_text + footer)
        
        # Save AI response to history
        db.add_chat_history(user.id, chat.id, sent_message.message_id,
                           'assistant', response_text, provider, model)
        
        # Update usage stats
        db.add_usage_stat(user.id, chat.id, provider, model, result.get('tokens', 0))
    else:
        await update.message.reply_text(
            f"❌ **Error:** {result['error']}",
            parse_mode=ParseMode.MARKDOWN
        )

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /Nerd command"""
    await nerd_command(update, context)

async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /projects command"""
    projects_text = f"""
📁 **{config.CREATOR_NAME}'s Projects**

"""
    
    keyboard = []
    for name, info in config.PROJECTS.items():
        projects_text += f"**🔹 {name}**\n{info['description']}\n\n"
        keyboard.append([InlineKeyboardButton(f"🔗 {name}", url=info['url'])])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        projects_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def enhancify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /enhancify command"""
    info = config.PROJECTS.get("Enhancify", {})
    
    text = f"""
📱 **Enhancify**

{info.get('description', 'A powerful enhancement tool for Android apps')}

**Features:**
• Classic Revancify v1 UI with modern tweaks
• Cybernetic Green theme by Graywizard888
• File manager-like selection interface
• Network acceleration for faster downloads
• Pre-release support (CLI, Patches, Options)
• Auto-launch when updated, instantly launch when first time installed
• Modern Tweaks For Improving Github Api Performance and Apkmirror Reliability
• Custom Github Token Support (5000/Hr) Rate Limit
• Rish Apk Installation Support with (Dex Optimizer/Playstore Spoof installed)
• Custom sources management (add/edit/delete)
• Custom Keystore Support
• Import apps when APKMirror Api fails
• Supports APK, APKM, XAPK File formats
• XAPK Custom language selection support
• Optimize Libs (Aka Riplibs) Support For Apk Files

**Repository:** [Click here]({info.get('url', '#')})

Created by **{config.CREATOR_NAME}**
"""
    
    keyboard = [[InlineKeyboardButton("🔗 View on GitHub", url=info.get('url', '#'))]]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def terminalex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /terminalex command"""
    info = config.PROJECTS.get("Terminal Ex", {})
    
    text = f"""
💻 **Terminal Ex**

{info.get('description', 'Extended terminal with advanced features')}

**Features:**
• Fork Of termux-monet
• Extended terminal capabilities
• Advanced shell features
• Enhanced command execution
• Support latest android 


**Repository:** [Click here]({info.get('url', '#')})

Created by **{config.CREATOR_NAME}**
"""
    
    keyboard = [[InlineKeyboardButton("🔗 View on GitHub", url=info.get('url', '#'))]]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def aapt2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /aapt2 command"""
    info = config.PROJECTS.get("Custom-Enhancify-aapt2-binary", {})
    
    text = f"""
🔧 **Custom Enhancify aapt2 Binary**

{info.get('description', 'Custom aapt2 binary for Enhancify')}

**Features:**
• Custom aapt2 modifications
• Optimized for Enhancify
• Enhanced resource compilation

**Repository:** [Click here]({info.get('url', '#')})

Created by **{config.CREATOR_NAME}**
"""
    
    keyboard = [[InlineKeyboardButton("🔗 View on GitHub", url=info.get('url', '#'))]]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /models command"""
    user = update.effective_user
    settings = db.get_user_settings(user.id) or {}
    
    current_provider = settings.get('ai_provider', config.DEFAULT_AI_PROVIDER)
    current_model = settings.get(f'{current_provider}_model',
                                  config.DEFAULT_OPENAI_MODEL if current_provider == 'openai' 
                                  else config.DEFAULT_GEMINI_MODEL)
    
    text = f"""
🤖 **AI Model Settings**

**Current Provider:** {current_provider.upper()}
**Current Model:** {current_model}

Select a provider and model below:
"""
    
    keyboard = [
        [InlineKeyboardButton("🔷 OpenAI/ChatGPT", callback_data="provider_openai")],
        [InlineKeyboardButton("🔶 Google Gemini", callback_data="provider_gemini")],
        [InlineKeyboardButton("📋 View All Models", callback_data="view_models")]
    ]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def provider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /provider command"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/provider <openai|gemini>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    provider = context.args[0].lower()
    if provider not in ['openai', 'gemini', 'chatgpt']:
        await update.message.reply_text(
            "❌ Invalid provider. Use `openai` or `gemini`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if provider == 'chatgpt':
        provider = 'openai'
    
    db.set_user_settings(user.id, user.username, ai_provider=provider)
    
    await update.message.reply_text(
        f"✅ AI provider switched to **{provider.upper()}**",
        parse_mode=ParseMode.MARKDOWN
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command"""
    user = update.effective_user
    chat = update.effective_chat
    
    user_settings = db.get_user_settings(user.id) or {}
    
    text = f"""
⚙️ **Your Settings**

**User ID:** `{user.id}`
**Username:** @{user.username or 'Not set'}

**AI Settings:**
• Provider: {user_settings.get('ai_provider', config.DEFAULT_AI_PROVIDER).upper()}
• OpenAI Model: {user_settings.get('openai_model', config.DEFAULT_OPENAI_MODEL)}
• Gemini Model: {user_settings.get('gemini_model', config.DEFAULT_GEMINI_MODEL)}
"""
    
    # Add group settings if in a group
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        group_settings = db.get_group_settings(chat.id) or {}
        text += f"""
**Group Settings:**
• AI Enabled: {'✅' if group_settings.get('ai_enabled', True) else '❌'}
• Admin Only AI: {'✅' if group_settings.get('admin_only_ai', False) else '❌'}
• Welcome Enabled: {'✅' if group_settings.get('welcome_enabled', True) else '❌'}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Change Provider", callback_data="models")],
        [InlineKeyboardButton("📊 My Stats", callback_data="mystats")]
    ]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystats command"""
    user = update.effective_user
    
    stats = db.get_usage_stats(user_id=user.id)
    
    if not stats:
        await update.message.reply_text("📊 No usage statistics yet!")
        return
    
    text = f"""
📊 **Your Usage Statistics**

"""
    
    total_requests = 0
    total_tokens = 0
    
    for stat in stats:
        text += f"**{stat['ai_provider'].upper()} - {stat['model']}**\n"
        text += f"  • Requests: {stat['requests']}\n"
        text += f"  • Tokens: {stat['total_tokens'] or 'N/A'}\n\n"
        total_requests += stat['requests']
        total_tokens += stat['total_tokens'] or 0
    
    text += f"**Total Requests:** {total_requests}\n"
    text += f"**Total Tokens:** {total_tokens}"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command"""
    user = update.effective_user
    chat = update.effective_chat
    
    db.clear_chat_history(chat.id, user.id)
    
    await update.message.reply_text("🗑️ Chat history cleared!")

# ==================== GROUP ADMIN COMMANDS ====================

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    target_user = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text(
            "❌ Please reply to a user's message or provide a user ID.\n"
            "Usage: `/ban` (reply) or `/ban <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else None
    success, message = await group_ops.ban_member(update, context, target_user.id, reason)
    
    await update.message.reply_text(message)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/unban <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    success, message = await group_ops.unban_member(update, context, user_id)
    await update.message.reply_text(message)

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kick command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    target_user = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text(
            "❌ Please reply to a user's message or provide a user ID.\n"
            "Usage: `/kick` (reply) or `/kick <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else None
    success, message = await group_ops.kick_member(update, context, target_user.id, reason)
    
    await update.message.reply_text(message)

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mute command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    target_user = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text(
            "❌ Please reply to a user's message.\n"
            "Usage: `/mute [duration]` (reply)\n"
            "Duration: 30s, 5m, 1h, 1d",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    duration = None
    if context.args:
        duration = parse_duration(context.args[0])
    
    success, message = await group_ops.mute_member(update, context, target_user.id, duration)
    await update.message.reply_text(message)

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    target_user = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text(
            "❌ Please reply to a user's message.\n"
            "Usage: `/unmute` (reply)",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    success, message = await group_ops.unmute_member(update, context, target_user.id)
    await update.message.reply_text(message)

async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /promote command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    target_user = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text(
            "❌ Please reply to a user's message.\n"
            "Usage: `/promote [title]` (reply)",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    title = ' '.join(context.args) if context.args else None
    success, message = await group_ops.promote_member(update, context, target_user.id, title)
    
    await update.message.reply_text(message)

async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /demote command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    target_user = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text(
            "❌ Please reply to a user's message.\n"
            "Usage: `/demote` (reply)",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    success, message = await group_ops.demote_member(update, context, target_user.id)
    await update.message.reply_text(message)

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pin command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Please reply to the message you want to pin.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    notify = 'silent' not in (context.args[0].lower() if context.args else '')
    success, message = await group_ops.pin_message(
        update, context, 
        update.message.reply_to_message.message_id,
        notify
    )
    
    await update.message.reply_text(message)

async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unpin command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    message_id = None
    if update.message.reply_to_message:
        message_id = update.message.reply_to_message.message_id
    
    success, message = await group_ops.unpin_message(update, context, message_id)
    await update.message.reply_text(message)

async def chatinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chatinfo command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    info = await group_ops.get_chat_info(update, context)
    
    if info['success']:
        text = f"""
📋 **Chat Information**

**Title:** {info['title']}
**ID:** `{info['id']}`
**Type:** {info['type']}
**Members:** {info['member_count']}
**Description:** {info.get('description') or 'Not set'}
"""
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Error: {info['error']}")

async def toggleai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /toggleai command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await group_ops.is_admin(update, context):
        await update.message.reply_text("❌ You need admin privileges!")
        return
    
    settings = db.get_group_settings(update.effective_chat.id) or {}
    current = settings.get('ai_enabled', True)
    new_value = not current
    
    db.set_group_settings(
        update.effective_chat.id,
        update.effective_chat.title,
        ai_enabled=new_value
    )
    
    status = "enabled ✅" if new_value else "disabled ❌"
    await update.message.reply_text(f"🤖 AI has been {status} for this group.")

async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setwelcome command"""
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await group_ops.is_admin(update, context):
        await update.message.reply_text("❌ You need admin privileges!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/setwelcome <message>`\n\n"
            "Variables:\n"
            "• `{name}` - User's name\n"
            "• `{username}` - User's username\n"
            "• `{chat}` - Chat title\n"
            "• `{count}` - Member count",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    welcome_message = ' '.join(context.args)
    db.set_group_settings(
        update.effective_chat.id,
        update.effective_chat.title,
        welcome_message=welcome_message
    )
    
    await update.message.reply_text("✅ Welcome message has been set!")

# ==================== CALLBACK HANDLERS ====================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "projects":
        await projects_callback(query, context)
    elif data == "settings":
        await settings_callback(query, context)
    elif data == "models":
        await models_callback(query, context)
    elif data == "help":
        await help_callback(query, context)
    elif data == "mystats":
        await mystats_callback(query, context)
    elif data.startswith("provider_"):
        await provider_callback(query, context, data)
    elif data.startswith("model_"):
        await model_callback(query, context, data)
    elif data == "view_models":
        await view_models_callback(query, context)
    elif data == "back_main":
        await back_to_main(query, context)

async def projects_callback(query, context):
    """Handle projects callback"""
    projects_text = f"📁 **{config.CREATOR_NAME}'s Projects**\n\n"
    
    keyboard = []
    for name, info in config.PROJECTS.items():
        projects_text += f"**🔹 {name}**\n{info['description']}\n\n"
        keyboard.append([InlineKeyboardButton(f"🔗 {name}", url=info['url'])])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    
    await query.edit_message_text(
        projects_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_callback(query, context):
    """Handle settings callback"""
    user = query.from_user
    user_settings = db.get_user_settings(user.id) or {}
    
    text = f"""
⚙️ **Your Settings**

**AI Settings:**
• Provider: {user_settings.get('ai_provider', config.DEFAULT_AI_PROVIDER).upper()}
• OpenAI Model: {user_settings.get('openai_model', config.DEFAULT_OPENAI_MODEL)}
• Gemini Model: {user_settings.get('gemini_model', config.DEFAULT_GEMINI_MODEL)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Change Provider", callback_data="models")],
        [InlineKeyboardButton("📊 My Stats", callback_data="mystats")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def models_callback(query, context):
    """Handle models callback"""
    user = query.from_user
    settings = db.get_user_settings(user.id) or {}
    
    current_provider = settings.get('ai_provider', config.DEFAULT_AI_PROVIDER)
    
    text = f"""
🤖 **AI Model Settings**

**Current Provider:** {current_provider.upper()}

Select a provider:
"""
    
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if current_provider == 'openai' else ''}🔷 OpenAI/ChatGPT", 
            callback_data="provider_openai"
        )],
        [InlineKeyboardButton(
            f"{'✅ ' if current_provider == 'gemini' else ''}🔶 Google Gemini", 
            callback_data="provider_gemini"
        )],
        [InlineKeyboardButton("📋 View All Models", callback_data="view_models")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_callback(query, context):
    """Handle help callback"""
    help_text = f"""
📖 **{config.BOT_NAME} Quick Help**

**Main Commands:**
• `/Nerd <question>` - Ask me anything
• `/models` - Switch AI models
• `/projects` - View projects
• `/settings` - Your settings

**Admin Commands:**
• `/ban`, `/kick`, `/mute`
• `/promote`, `/demote`
• `/pin`, `/unpin`

Use `/help` for full command list.
"""
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]
    
    await query.edit_message_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def mystats_callback(query, context):
    """Handle mystats callback"""
    user = query.from_user
    stats = db.get_usage_stats(user_id=user.id)
    
    if not stats:
        text = "📊 No usage statistics yet!"
    else:
        text = "📊 **Your Usage Statistics**\n\n"
        total_requests = 0
        
        for stat in stats:
            text += f"**{stat['ai_provider'].upper()} - {stat['model']}**\n"
            text += f"  • Requests: {stat['requests']}\n\n"
            total_requests += stat['requests']
        
        text += f"**Total Requests:** {total_requests}"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="settings")]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def provider_callback(query, context, data):
    """Handle provider selection callback"""
    user = query.from_user
    provider = data.replace("provider_", "")
    
    db.set_user_settings(user.id, user.username, ai_provider=provider)
    
    # Show model selection for the provider
    if provider == "openai":
        models = config.OPENAI_MODELS
    else:
        models = config.GEMINI_MODELS
    
    settings = db.get_user_settings(user.id) or {}
    current_model = settings.get(f'{provider}_model', models[0])
    
    text = f"""
🤖 **{provider.upper()} Models**

Select a model:
"""
    
    keyboard = []
    for model in models[:8]:  # Show first 8 models
        prefix = "✅ " if model == current_model else ""
        keyboard.append([InlineKeyboardButton(
            f"{prefix}{model}", 
            callback_data=f"model_{provider}_{model}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="models")])
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def model_callback(query, context, data):
    """Handle model selection callback"""
    user = query.from_user
    parts = data.replace("model_", "").split("_", 1)
    provider = parts[0]
    model = parts[1]
    
    db.set_user_settings(
        user.id, 
        user.username,
        ai_provider=provider,
        **{f'{provider}_model': model}
    )
    
    await query.answer(f"✅ Model set to {model}")
    
    # Refresh the model selection screen
    await provider_callback(query, context, f"provider_{provider}")

async def view_models_callback(query, context):
    """Handle view all models callback"""
    text = """
📋 **Available AI Models**

**🔷 OpenAI/ChatGPT:**
"""
    for model in config.OPENAI_MODELS:
        text += f"• {model}\n"
    
    text += "\n**🔶 Google Gemini:**\n"
    for model in config.GEMINI_MODELS:
        text += f"• {model}\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="models")]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def back_to_main(query, context):
    """Handle back to main menu"""
    text = f"""
🤖 **{config.BOT_NAME}**

What would you like to do?
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📚 Projects", callback_data="projects"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("🤖 Models", callback_data="models"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== MESSAGE HANDLERS ====================

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle replies to bot messages"""
    message = update.message
    user = update.effective_user
    chat = update.effective_chat
    
    # Check if it's a reply to the bot's message
    if not message.reply_to_message:
        return
    
    if message.reply_to_message.from_user.id != context.bot.id:
        return
    
    # Check if AI is enabled in group
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        settings = db.get_group_settings(chat.id) or {}
        if not settings.get('ai_enabled', True):
            return
    
    # Process as AI query
    question = message.text
    if not question:
        return
    
    # Get settings
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        settings = db.get_group_settings(chat.id) or {}
    else:
        settings = db.get_user_settings(user.id) or {}
    
    provider = settings.get('ai_provider', config.DEFAULT_AI_PROVIDER)
    model = settings.get(f'{provider}_model',
                         config.DEFAULT_OPENAI_MODEL if provider == 'openai' 
                         else config.DEFAULT_GEMINI_MODEL)
    
    # Show typing
    await context.bot.send_chat_action(chat.id, "typing")
    
    # Get context from replied message
    chat_history = db.get_chat_history(chat.id, limit=10)
    
    # Generate response
    result = await ai_handler.generate_response(
        prompt=question,
        provider=provider,
        model=model,
        chat_history=chat_history
    )
    
    if result['success']:
        response_text = result['response']
        footer = f"\n\n_🤖 {result['model']} | {result['provider'].upper()}_"
        
        try:
            sent = await message.reply_text(
                response_text + footer,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            sent = await message.reply_text(response_text + footer)
        
        # Save to history
        db.add_chat_history(user.id, chat.id, message.message_id,
                           'user', question, provider, model)
        db.add_chat_history(user.id, chat.id, sent.message_id,
                           'assistant', response_text, provider, model)
        db.add_usage_stat(user.id, chat.id, provider, model, result.get('tokens', 0))
    else:
        await message.reply_text(f"❌ Error: {result['error']}")

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining the group"""
    chat = update.effective_chat
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        settings = db.get_group_settings(chat.id) or {}
        
        if not settings.get('welcome_enabled', True):
            continue
        
        welcome_message = settings.get('welcome_message')
        
        if not welcome_message:
            welcome_message = f"""
👋 Welcome to **{chat.title}**, {member.first_name}!

I'm **{config.BOT_NAME}**, your AI assistant here.

Use `/Nerd <question>` to ask me anything!
"""
        else:
            # Replace variables
            member_count = await context.bot.get_chat_member_count(chat.id)
            welcome_message = welcome_message.format(
                name=member.first_name,
                username=f"@{member.username}" if member.username else member.first_name,
                chat=chat.title,
                count=member_count
            )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Exception while handling update: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again."
        )

# ==================== HEALTH CHECK FOR RENDER ====================

from aiohttp import web

async def health_check(request):
    """Health check endpoint for Render"""
    return web.Response(text="OK", status=200)

async def start_health_server():
    """Start health check server"""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    port = int(os.getenv("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server started on port {port}")

# ==================== MAIN ====================

async def set_bot_commands(application):
    """Set bot commands for menu"""
    commands = [
        BotCommand("nerd", "Ask me anything"),
        BotCommand("help", "Show help message"),
        BotCommand("projects", "View creator's projects"),
        BotCommand("models", "Switch AI models"),
        BotCommand("settings", "View your settings"),
        BotCommand("mystats", "View usage statistics"),
        BotCommand("clear", "Clear chat history"),
        BotCommand("chatinfo", "Get chat information (groups)"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    """Main function to run the bot"""
    # Validate configuration
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    
    if not config.OPENAI_API_KEY and not config.GEMINI_API_KEY:
        logger.warning("No AI API keys configured. AI features will be limited.")
    
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("Nerd", nerd_command))
    application.add_handler(CommandHandler("nerd", nerd_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("projects", projects_command))
    application.add_handler(CommandHandler("enhancify", enhancify_command))
    application.add_handler(CommandHandler("terminalex", terminalex_command))
    application.add_handler(CommandHandler("aapt2", aapt2_command))
    application.add_handler(CommandHandler("models", models_command))
    application.add_handler(CommandHandler("provider", provider_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Group admin commands
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("kick", kick_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("promote", promote_command))
    application.add_handler(CommandHandler("demote", demote_command))
    application.add_handler(CommandHandler("pin", pin_command))
    application.add_handler(CommandHandler("unpin", unpin_command))
    application.add_handler(CommandHandler("chatinfo", chatinfo_command))
    application.add_handler(CommandHandler("toggleai", toggleai_command))
    application.add_handler(CommandHandler("setwelcome", setwelcome_command))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.REPLY & filters.TEXT & ~filters.COMMAND,
        handle_reply
    ))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handle_new_member
    ))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start health check server for Render
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_health_server())
    
    # Set bot commands
    loop.run_until_complete(set_bot_commands(application))
    
    # Start the bot
    logger.info(f"Starting {config.BOT_NAME}...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
