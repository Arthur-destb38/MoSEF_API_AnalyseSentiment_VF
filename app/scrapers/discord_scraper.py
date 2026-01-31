"""
Discord Scraper
"""

import os
import asyncio
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict

from dotenv import load_dotenv

try:
    import discord
    from discord.ext import commands
    DISCORD_OK = True
except ImportError:
    DISCORD_OK = False
    discord = None
    commands = None

try:
    from app.storage import save_posts
except Exception:
    save_posts = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LIMITS = {"bot": 1000}

CRYPTO_SERVERS = {
    "cryptocommunity": "Crypto Community",
    "defi": "DeFi Discussions",
}


def get_limits():
    return LIMITS


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("@everyone", "").replace("@here", "")
    return text.strip()


async def _scrape_channel_async(
    bot_token: str,
    channel_id: int,
    limit: int = 100,
    after_message_id: Optional[int] = None
) -> List[Dict]:
    if not DISCORD_OK:
        raise ImportError("discord.py n'est pas installé. Installez-le avec: poetry add discord.py")
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.messages = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    messages = []
    
    @bot.event
    async def on_ready():
        logger.info(f"Bot connecté: {bot.user}")
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                logger.error(f"Salon {channel_id} introuvable ou bot non invité")
                await bot.close()
                return
            
            logger.info(f"Scraping {channel.name}")
            
            fetched = []
            async for message in channel.history(
                limit=limit,
                after=discord.Object(id=after_message_id) if after_message_id else None
            ):
                fetched.append(message)
            
            for msg in fetched:
                created_utc = msg.created_at.timestamp()
                reactions = []
                for reaction in msg.reactions:
                    reactions.append({
                        "emoji": str(reaction.emoji),
                        "count": reaction.count
                    })
                
                messages.append({
                    "id": str(msg.id),
                    "text": _clean_text(msg.content),
                    "author": msg.author.name if msg.author else None,
                    "author_id": str(msg.author.id) if msg.author else None,
                    "created_utc": str(created_utc),
                    "channel": channel.name,
                    "channel_id": str(channel_id),
                    "guild": channel.guild.name if channel.guild else None,
                    "guild_id": str(channel.guild.id) if channel.guild else None,
                    "reactions": reactions,
                    "attachments": len(msg.attachments),
                    "embeds": len(msg.embeds),
                    "source": "discord",
                    "method": "bot",
                    "url": f"https://discord.com/channels/{channel.guild.id}/{channel_id}/{msg.id}" if channel.guild else None,
                })
            
            logger.info(f"Done: {len(messages)} messages")
            
        except Exception as e:
            logger.error(f"Erreur scraping Discord: {e}")
        finally:
            await bot.close()
    
    try:
        await bot.start(bot_token)
    except discord.LoginFailure:
        logger.error("Token Discord invalide")
        raise
    except Exception as e:
        logger.error(f"Erreur connexion Discord: {e}")
        raise
    
    return messages


def scrape_discord(
    channel_id: str,
    limit: int = 100,
    bot_token: Optional[str] = None,
    after_message_id: Optional[str] = None
) -> List[Dict]:
    if not DISCORD_OK:
        logger.error("discord.py n'est pas installé")
        return []
    
    if not bot_token:
        load_dotenv()
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN manquant dans .env")
        return []
    
    try:
        channel_id_int = int(channel_id)
    except ValueError:
        logger.error(f"channel_id invalide: {channel_id} (doit être un nombre)")
        return []
    
    # Convertir after_message_id si fourni
    after_id_int = None
    if after_message_id:
        try:
            after_id_int = int(after_message_id)
        except ValueError:
            logger.warning(f"after_message_id invalide: {after_message_id}")
    
    limit = min(limit, 1000)
    
    try:
        messages = asyncio.run(_scrape_channel_async(
            bot_token=bot_token,
            channel_id=channel_id_int,
            limit=limit,
            after_message_id=after_id_int
        ))
        return messages
    except Exception as e:
        logger.error(f"Erreur scraping Discord: {e}")
        return []


def scrape_multiple_channels(
    channel_ids: List[str],
    limit_per_channel: int = 100,
    bot_token: Optional[str] = None
) -> List[Dict]:
    all_messages = []
    for channel_id in channel_ids:
        logger.info(f"Scraping salon {channel_id}...")
        messages = scrape_discord(
            channel_id=channel_id,
            limit=limit_per_channel,
            bot_token=bot_token
        )
        all_messages.extend(messages)
        time.sleep(1)
    
    return all_messages
