"""
Discord Scraper - Bot API (discord.py)
Scrape les messages depuis des serveurs Discord via bot

Nécessite:
1. Un bot Discord (créer sur https://discord.com/developers/applications)
2. Le bot doit être invité dans les serveurs avec permissions "Read Message History"
3. Un token bot dans .env: DISCORD_BOT_TOKEN=ton_token
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
import logging

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

# Limites
LIMITS = {
    "bot": 1000,  # ~1000 messages max par salon (rate limits)
}

# Serveurs crypto populaires (IDs à configurer)
CRYPTO_SERVERS = {
    # Exemples - à remplacer par les vrais IDs
    "cryptocommunity": "Crypto Community",
    "defi": "DeFi Discussions",
}


def get_limits():
    """Retourne les limites"""
    return LIMITS


def _clean_text(text: str) -> str:
    """Nettoie le texte d'un message Discord"""
    if not text:
        return ""
    # Enlever les mentions, emojis custom, etc.
    text = text.replace("@everyone", "").replace("@here", "")
    # Enlever les URLs si besoin
    return text.strip()


async def _scrape_channel_async(
    bot_token: str,
    channel_id: int,
    limit: int = 100,
    after_message_id: Optional[int] = None
) -> List[Dict]:
    """
    Scrape asynchrone d'un salon Discord
    
    Args:
        bot_token: Token du bot Discord
        channel_id: ID du salon (int)
        limit: Nombre max de messages
        after_message_id: ID du message après lequel commencer (pour pagination)
    
    Returns:
        Liste de messages formatés
    """
    if not DISCORD_OK:
        raise ImportError("discord.py n'est pas installé. Installez-le avec: poetry add discord.py")
    
    intents = discord.Intents.default()
    intents.message_content = True  # Nécessaire pour lire le contenu des messages
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
            
            logger.info(f"Scraping salon: {channel.name} (serveur: {channel.guild.name})")
            
            # Récupérer les messages
            fetched = []
            async for message in channel.history(
                limit=limit,
                after=discord.Object(id=after_message_id) if after_message_id else None
            ):
                fetched.append(message)
            
            # Formater les messages
            for msg in fetched:
                # Ignorer les messages de bots si besoin
                # if msg.author.bot:
                #     continue
                
                # Date en timestamp Unix
                created_utc = msg.created_at.timestamp()
                
                # Réactions
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
            
            logger.info(f"[Discord] {len(messages)} messages récupérés depuis {channel.name}")
            
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
    """
    Scrape un salon Discord (wrapper synchrone)
    
    Args:
        channel_id: ID du salon (string, sera converti en int)
        limit: Nombre max de messages (max ~1000)
        bot_token: Token du bot (si None, cherche dans .env)
        after_message_id: ID du message après lequel commencer
    
    Returns:
        Liste de messages formatés
    """
    if not DISCORD_OK:
        logger.error("discord.py n'est pas installé")
        return []
    
    # Récupérer le token
    if not bot_token:
        from dotenv import load_dotenv
        load_dotenv()
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN manquant dans .env")
        return []
    
    # Convertir channel_id en int
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
    
    # Limiter à 1000 pour éviter les rate limits
    limit = min(limit, 1000)
    
    # Lancer le scraping asynchrone
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
    """
    Scrape plusieurs salons Discord
    
    Args:
        channel_ids: Liste d'IDs de salons
        limit_per_channel: Limite par salon
        bot_token: Token du bot
    
    Returns:
        Liste combinée de tous les messages
    """
    all_messages = []
    for channel_id in channel_ids:
        logger.info(f"Scraping salon {channel_id}...")
        messages = scrape_discord(
            channel_id=channel_id,
            limit=limit_per_channel,
            bot_token=bot_token
        )
        all_messages.extend(messages)
        # Petit délai entre les salons
        import time
        time.sleep(1)
    
    return all_messages
