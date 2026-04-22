import os
import asyncio
import discord
import sqlite3
import json
import re
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timezone
from logger_config import log

# Intents setup for message reading and guild access
intents = discord.Intents.default()
intents.message_content = True 
intents.guilds = True

# Initialize bot with prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Database configuration
DB_PATH = "jobs_detail.db"
load_dotenv()

# Database connection 
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Helper for validation
def _is_valid(value) -> bool:
    """Check if a value is meaningful (not None, not 0, not empty string, not 'NA')."""
    if value is None:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    val_str = str(value).strip()
    if val_str == "" or val_str.upper() == "NA":
        return False
    return True

# Field formatters
def _format_budget(job: sqlite3.Row) -> str:
    """Formats budget based on job type; returns None if no data available."""
    job_type = str(job["job_type"] or "").upper()

    if job_type == "HOURLY":
        low = job["hourly_min"]
        high = job["hourly_max"]
        if _is_valid(low) and _is_valid(high):
            return f"${low:.0f} – ${high:.0f} / hr"
        if _is_valid(low):
            return f"${low:.0f}+ / hr"
    else:
        amount = job["budget_amount"]
        if _is_valid(amount):
            return f"${amount:,.0f} Fixed"
    
    return None

def _format_duration(raw: str) -> str:
    """Maps duration codes to readable text."""
    if not _is_valid(raw):
        return None
    mapping = {
        "WEEK": "Less than a week",
        "MONTH": "Less than a month",
        "SEMESTER": "1 – 3 months",
        "ONGOING": "More than 3 months",
    }
    return mapping.get(raw.upper(), raw)


def _format_tier(tier) -> str:
    """Maps numeric tier or string labels to experience levels."""
    if not _is_valid(tier):
        return None
    
    # Agar data already string hai (e.g., 'IntermediateLevel')
    tier_str = str(tier).strip()
    
    # Mapping for both integers and strings
    mapping = {
        "1": "Entry Level",
        "2": "Intermediate",
        "3": "Expert",
        "ENTRYLEVEL": "Entry Level",
        "INTERMEDIATELEVEL": "Intermediate",
        "EXPERTLEVEL": "Expert"
    }
    
    # Clean string for comparison
    clean_key = tier_str.upper().replace(" ", "")
    return mapping.get(clean_key, tier_str) # Agar map na ho to asli value dikha de

def _format_skills(raw: str) -> str:
    """Parses JSON skills or returns clean string."""
    if not _is_valid(raw):
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            skills = ", ".join(str(s) for s in parsed if s)
            return skills if skills.strip() else None
    except (json.JSONDecodeError, TypeError):
        pass
    return raw.strip()

def _format_time_ago(iso_str: str) -> str:
    """Converts ISO timestamp to relative time string."""
    if not _is_valid(iso_str):
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff_seconds = int((now - dt).total_seconds())

        if diff_seconds < 60: return "Just now"
        if diff_seconds < 3600:
            mins = diff_seconds // 60
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        if diff_seconds < 86400:
            hrs = diff_seconds // 3600
            return f"{hrs} hour{'s' if hrs != 1 else ''} ago"
        
        days = diff_seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return None

def build_job_embed(job: sqlite3.Row) -> discord.Embed:
    """Constructs a Discord embed, omitting fields that have no data."""

    # Retrieve data from row
    job_id = job["job_id"]
    title = job["title"]
    description = job["description"]
    job_type = job["job_type"]
    
    # FIX: Correct column name (url instead of job_url)
    job_url = job["url"] if _is_valid(job["url"]) else None

    # Get formatted values
    skills = _format_skills(job["skills"])
    budget = _format_budget(job)
    duration = _format_duration(job["duration"])
    tier = _format_tier(job["contractor_tier"])
    posted_ago = _format_time_ago(job["published_time"])
    first_seen = job["first_seen_at"] if _is_valid(job["first_seen_at"]) else None

    # Description Preview (safe handling)
    desc_text = str(description) if description else "No description available"
    if len(desc_text) > 350:
        desc_text = desc_text[:347] + "..."

    # Determine Color
    colour_map = {"FIXED": 0x1DBF73, "HOURLY": 0x14A8FF}
    colour = colour_map.get(str(job_type).upper(), 0x888888)

    embed = discord.Embed(
        title=f"🆕 {title}",
        url=job_url if job_url else discord.Embed.Empty,
        description=f"```{desc_text}```",
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )

    # Add fields only if valid
    if budget:
        embed.add_field(name="💰 Budget", value=f"**{budget}**", inline=True)
    
    if _is_valid(job_type):
        embed.add_field(name="📋 Job Type", value=f"**{job_type}**", inline=True)

    if tier:
        embed.add_field(name="🎯 Experience Level", value=f"**{tier}**", inline=True)

    if duration:
        embed.add_field(name="⏳ Duration", value=f"**{duration}**", inline=True)

    if skills:
        embed.add_field(name="🛠️ Skills Required", value=skills, inline=False)

    if posted_ago:
        embed.add_field(name="🕐 Posted", value=posted_ago, inline=True)

    if first_seen:
        embed.add_field(name="👁️ First Seen", value=first_seen, inline=True)

    if job_url:
        embed.add_field(
            name="🔗 Apply",
            value=f"[Click here to apply on Upwork]({job_url})",
            inline=False,
        )

    embed.set_footer(text=f"Job ID: {job_id} • Powered by Upwork Bot")
    return embed


# Main processing function to fetch job details and post to Discord
async def post_job_to_discord(bot: discord.Client, channel_id: int, job_id: str) -> bool:
    """Fetches job from DB and posts it to the specified channel."""
    log.info(f"---Fetching job '{job_id}' from database...")

    try:
        conn = get_connection()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
    except Exception as e:
        log.error(f"❌ Error reading database: {e}")
        return False

    if not row:
        log.warning(f"⚠️ Warning: Job '{job_id}' not found.")
        return False

    channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    log.info(f"--- Found channel: {channel.name} ---")
    try:
        embed = build_job_embed(row)
        message = await channel.send(embed=embed)

        conn = get_connection()
        conn.execute("UPDATE jobs SET discord_posted = 1 WHERE job_id = ?", (job_id,))
        conn.commit()
        conn.close()

        log.info(f"✅ Success: Posted to {channel_id}. Message ID: {message.id}")
        return True
    except Exception as e:
        log.error(f"❌ Error during posting: {e}")
        return False



# Function to post a job and exit 
async def discord_post(channel_id: int, job_id: str):
    bot_client = discord.Client(intents=intents)

    @bot_client.event
    async def on_ready():
        log.info(f"✅  --- Bot Connected as {bot_client.user} ---")
        try:
            await post_job_to_discord(bot_client, channel_id, job_id)
        finally:
            log.info("✅  --- Task Finished. Closing connection. ---")
            await bot_client.close()
            await asyncio.sleep(1)  # Ensure clean shutdown

    token = os.getenv("DISCORD_TOKEN")
    if token:
        await bot_client.start(token)
    else:
        log.error("❌ Error: DISCORD_TOKEN missing.")
    log.info("✅  --- Bot Disconnected ---\n")


"""
# TESTING BLOCK
asyncio.run(discord_post(channel_id=1495486908254523482, job_id="2038581551442065747"))
"""