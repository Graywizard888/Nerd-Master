import logging
from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import ContextTypes
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GroupOperations:
    """Handles group administration operations"""
    
    @staticmethod
    async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None) -> bool:
        """Check if user is admin in the chat"""
        try:
            user_id = user_id or update.effective_user.id
            chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    @staticmethod
    async def is_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if bot is admin in the chat"""
        try:
            bot_member = await context.bot.get_chat_member(
                update.effective_chat.id, 
                context.bot.id
            )
            return bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except Exception as e:
            logger.error(f"Error checking bot admin status: {e}")
            return False
    
    @staticmethod
    async def kick_member(
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE, 
        user_id: int,
        reason: str = None
    ) -> Tuple[bool, str]:
        """Kick a member from the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to kick members or ask my Master."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my Master to promote you."
            
            # Check if target is admin
            target_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            if target_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                return False, "❌ I cannot kick administrators nor betray my Master."
            
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            
            reason_text = f"\nReason: {reason}" if reason else ""
            return True, f"✅ I kicked the user from the group.{reason_text}"
            
        except Exception as e:
            logger.error(f"Error kicking member: {e}")
            return False, f"❌ Sorry, 😔 I failed to kick member: {str(e)}"
    
    @staticmethod
    async def ban_member(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        reason: str = None
    ) -> Tuple[bool, str]:
        """Ban a member from the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to ban members."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            target_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            if target_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                return False, "❌ Cannot ban administrators, I won't betray my admins."
            
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            
            reason_text = f"\nReason: {reason}" if reason else ""
            return True, f"🔨 User has been banned from the group.{reason_text}"
            
        except Exception as e:
            logger.error(f"Error banning member: {e}")
            return False, f"❌ Failed to ban member: {str(e)}"
    
    @staticmethod
    async def unban_member(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int
    ) -> Tuple[bool, str]:
        """Unban a member from the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to unban members."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            return True, "✅ User has been unbanned. They can now rejoin the group."
            
        except Exception as e:
            logger.error(f"Error unbanning member: {e}")
            return False, f"❌ Failed to unban member: {str(e)}"
    
    @staticmethod
    async def mute_member(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        duration: int = None  # Duration in seconds
    ) -> Tuple[bool, str]:
        """Mute a member in the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to mute members."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            target_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            if target_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                return False, "❌ Cannot mute administrators, I won't betray my admins."
            
            permissions = ChatPermissions(can_send_messages=False)
            
            if duration:
                until_date = datetime.now() + timedelta(seconds=duration)
                await context.bot.restrict_chat_member(
                    update.effective_chat.id, 
                    user_id, 
                    permissions,
                    until_date=until_date
                )
                if duration >= 86400:
                    duration_text = f" for {duration // 86400} day(s)"
                elif duration >= 3600:
                    duration_text = f" for {duration // 3600} hour(s)"
                elif duration >= 60:
                    duration_text = f" for {duration // 60} minute(s)"
                else:
                    duration_text = f" for {duration} second(s)"
            else:
                await context.bot.restrict_chat_member(
                    update.effective_chat.id, 
                    user_id, 
                    permissions
                )
                duration_text = " indefinitely"
            
            return True, f"🔇 User has been muted{duration_text}."
            
        except Exception as e:
            logger.error(f"Error muting member: {e}")
            return False, f"❌ Failed to mute member: {str(e)}"
    
    @staticmethod
    async def unmute_member(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int
    ) -> Tuple[bool, str]:
        """Unmute a member in the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to unmute members."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            
            await context.bot.restrict_chat_member(
                update.effective_chat.id, 
                user_id, 
                permissions
            )
            
            return True, "🔊 User has been unmuted."
            
        except Exception as e:
            logger.error(f"Error unmuting member: {e}")
            return False, f"❌ Failed to unmute member: {str(e)}"
    
    @staticmethod
    async def promote_member(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        title: str = None
    ) -> Tuple[bool, str]:
        """Promote a member to admin"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to promote members."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            await context.bot.promote_chat_member(
                update.effective_chat.id,
                user_id,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_manage_video_chats=True
            )
            
            if title:
                try:
                    await context.bot.set_chat_administrator_custom_title(
                        update.effective_chat.id,
                        user_id,
                        title
                    )
                except Exception:
                    pass  # Title setting might fail but promotion succeeded
            
            return True, "👑 User has been promoted to admin."
            
        except Exception as e:
            logger.error(f"Error promoting member: {e}")
            return False, f"❌ Failed to promote member: {str(e)}"
    
    @staticmethod
    async def demote_member(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int
    ) -> Tuple[bool, str]:
        """Demote an admin to regular member"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to demote members."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            await context.bot.promote_chat_member(
                update.effective_chat.id,
                user_id,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_manage_video_chats=False
            )
            
            return True, "📉 User has been demoted from admin."
            
        except Exception as e:
            logger.error(f"Error demoting member: {e}")
            return False, f"❌ Failed to demote member: {str(e)}"
    
    @staticmethod
    async def pin_message(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        message_id: int,
        notify: bool = True
    ) -> Tuple[bool, str]:
        """Pin a message in the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to pin messages."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            await context.bot.pin_chat_message(
                update.effective_chat.id,
                message_id,
                disable_notification=not notify
            )
            
            return True, "📌 Message has been pinned."
            
        except Exception as e:
            logger.error(f"Error pinning message: {e}")
            return False, f"❌ Failed to pin message: {str(e)}"
    
    @staticmethod
    async def unpin_message(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        message_id: int = None
    ) -> Tuple[bool, str]:
        """Unpin a message or all messages in the group"""
        try:
            if not await GroupOperations.is_bot_admin(update, context):
                return False, "❌ I need admin privileges to unpin messages."
            
            if not await GroupOperations.is_admin(update, context):
                return False, "❌ You need admin privileges to use this command or ask my master to promote you."
            
            if message_id:
                await context.bot.unpin_chat_message(update.effective_chat.id, message_id)
                return True, "📌 Message has been unpinned."
            else:
                await context.bot.unpin_all_chat_messages(update.effective_chat.id)
                return True, "📌 All messages have been unpinned."
            
        except Exception as e:
            logger.error(f"Error unpinning message: {e}")
            return False, f"❌ Failed to unpin message: {str(e)}"
    
    @staticmethod
    async def get_chat_info(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> dict:
        """Get information about the chat"""
        try:
            chat = await context.bot.get_chat(update.effective_chat.id)
            member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
            
            return {
                "success": True,
                "id": chat.id,
                "title": chat.title,
                "type": chat.type,
                "description": chat.description,
                "member_count": member_count,
                "invite_link": chat.invite_link
            }
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def get_member_info(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int
    ) -> dict:
        """Get information about a chat member"""
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            
            return {
                "success": True,
                "user_id": member.user.id,
                "username": member.user.username,
                "first_name": member.user.first_name,
                "last_name": member.user.last_name,
                "status": member.status,
                "is_bot": member.user.is_bot
            }
        except Exception as e:
            logger.error(f"Error getting member info: {e}")
            return {"success": False, "error": str(e)}

# Global group operations instance
group_ops = GroupOperations()
