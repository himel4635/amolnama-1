import discord
from discord.ext import commands
import json
import os
from datetime import datetime

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

HISTORY_FILE = "voice_history.json"
TOTALS_FILE = "user_totals.json"

voice_history = []
user_sessions = {}   # {member_id: datetime}
user_totals = {}     # {member_id: total_seconds}

# 🔧 Replace this with the ID of your dedicated text channel
LOG_CHANNEL_ID = 123456789012345678


# ------------------ Helper Functions ------------------
def load_data():
    global voice_history, user_totals
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            voice_history = json.load(f)
    else:
        voice_history = []

    if os.path.exists(TOTALS_FILE):
        with open(TOTALS_FILE, "r", encoding="utf-8") as f:
            user_totals = json.load(f)
    else:
        user_totals = {}


def save_data():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(voice_history, f, indent=2, ensure_ascii=False)

    with open(TOTALS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_totals, f, indent=2, ensure_ascii=False)


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: int) -> str:
    """Convert seconds to human-readable format"""
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}h {mins}m {secs}s"
    elif mins > 0:
        return f"{mins}m {secs}s"
    else:
        return f"{secs}s"


async def send_log(channel, member, action, color, description):
    """Send a styled embed log"""
    embed = discord.Embed(
        title=f"🎧 Voice Update: {action}",
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    await channel.send(embed=embed)


# ------------------ Bot Events ------------------
@bot.event
async def on_ready():
    load_data()
    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_voice_state_update(member, before, after):
    log = None
    action = None
    color = discord.Color.blue()
    description = None

    # User joined
    if before.channel is None and after.channel is not None:
        action = "Joined"
        log = f"[{timestamp()}] 🔊 {member.display_name} joined {after.channel.name}"
        description = f"🔊 **{member.mention}** joined **{after.channel.name}**"
        color = discord.Color.green()
        user_sessions[member.id] = datetime.utcnow()

    # User left
    elif before.channel is not None and after.channel is None:
        action = "Left"
        join_time = user_sessions.pop(member.id, None)
        duration_text = ""
        if join_time:
            duration = (datetime.utcnow() - join_time).total_seconds()
            # Update totals
            user_totals[str(member.id)] = user_totals.get(str(member.id), 0) + int(duration)
            duration_text = f" (Stayed: {format_duration(int(duration))})"

        log = f"[{timestamp()}] ❌ {member.display_name} left {before.channel.name}{duration_text}"
        description = f"❌ **{member.mention}** left **{before.channel.name}**{duration_text}"
        color = discord.Color.red()

    # User moved channels
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        action = "Moved"
        log = f"[{timestamp()}] ➡️ {member.display_name} moved from {before.channel.name} to {after.channel.name}"
        description = f"➡️ **{member.mention}** moved from **{before.channel.name}** → **{after.channel.name}**"
        color = discord.Color.orange()
        user_sessions[member.id] = datetime.utcnow()  # Reset timer for new channel

    if log:
        voice_history.append(log)
        save_data()
        print(log)

        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            await send_log(channel, member, action, color, description)


# ------------------ Commands ------------------
@bot.command()
async def vchistory(ctx, limit: int = 10):
    """Show recent voice channel join/leave history"""
    if not voice_history:
        await ctx.send("No voice history yet.")
        return

    logs = "\n".join(voice_history[-limit:])
    embed = discord.Embed(
        title="📜 Voice Channel History",
        description=f"```{logs}```",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)


@bot.command()
async def vcstats(ctx, member: discord.Member = None):
    """Show total voice time for a user"""
    member = member or ctx.author
    total_seconds = user_totals.get(str(member.id), 0)

    # If user is currently in VC, add live session time
    if member.id in user_sessions:
        join_time = user_sessions[member.id]
        total_seconds += int((datetime.utcnow() - join_time).total_seconds())

    embed = discord.Embed(
        title=f"📊 Voice Channel Stats for {member.display_name}",
        description=f"🕒 Total VC Time: **{format_duration(total_seconds)}**",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


# ------------------ Run ------------------
bot.run(os.getenv("DISCORD_TOKEN"))

