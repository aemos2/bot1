"""
Main entry point for the Multi-Purpose Executor Status Discord bot.
Works on any server — all alert/verification config is stored per-guild.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from utils.weao import (
    fetch_all_executors,
    fetch_roblox_version,
    load_cache,
    save_cache,
    load_roblox_cache,
    save_roblox_cache,
    get_all_alert_channels,
    ensure_data_dir,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Create a .env file from .env.example.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)


# ---------------------------------------------------------------------------
# Background checkers
# ---------------------------------------------------------------------------

async def _resolve_text_channel(channel_id: int) -> discord.TextChannel | None:
    """Resolve a channel even if it is not in the bot cache (multi-server safe)."""
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.warning("Could not fetch channel %s: %s", channel_id, e)
            return None
    if isinstance(channel, discord.TextChannel):
        return channel
    return None


@tasks.loop(minutes=5)
async def check_executor_updates():
    try:
        current = await fetch_all_executors()
        previous = load_cache()

        changes: list[str] = []
        new_cache: dict = {}

        for exe in current:
            title = exe.get("title")
            if not title:
                continue

            key = title.lower().strip()
            version = exe.get("version")
            updated_status = bool(exe.get("updateStatus", False))
            updated_date = exe.get("updatedDate")
            detected = bool(exe.get("detected", False))

            new_cache[key] = {
                "version": version,
                "updateStatus": updated_status,
                "updatedDate": updated_date,
                "detected": detected,
                "title": title,
            }

            old = previous.get(key)
            if old is None:
                # First time seeing this executor — baseline only, no alert
                continue

            old_version = old.get("version")
            old_status = bool(old.get("updateStatus", False))
            old_date = old.get("updatedDate")
            old_detected = bool(old.get("detected", False))

            if old_version != version and version is not None:
                changes.append(f"**{title}** updated to version `{version}`")
            elif (not old_status) and updated_status:
                changes.append(f"**{title}** is now **Updated** (v{version})")
            elif old_status and (not updated_status):
                changes.append(f"**{title}** is **no longer updated**")
            elif old_date and updated_date and old_date != updated_date and updated_status:
                # Same version string but new update date from WEAO
                changes.append(f"**{title}** re-confirmed updated (v{version}) — {updated_date}")

            if old_detected != detected:
                if detected:
                    changes.append(f"**{title}** is now **Detected**")
                else:
                    changes.append(f"**{title}** is now **Undetected**")

        save_cache(new_cache)

        if not changes:
            logger.debug("Executor checker: no changes")
            return

        logger.info("Executor changes detected: %s", changes)

        embed = discord.Embed(
            title="Executor Update Detected",
            description="\n".join(changes),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Automatic checker • weao.xyz • Multi-server")

        targets = get_all_alert_channels("executor")
        if not targets:
            logger.info("Executor changes found but no alert channels configured")
            return

        for guild_id, channel_id in targets:
            channel = await _resolve_text_channel(channel_id)
            if channel is None:
                logger.warning("Executor alert: invalid/missing channel %s (guild %s)", channel_id, guild_id)
                continue
            try:
                await channel.send(embed=embed)
                logger.info("Sent executor alert to channel %s (guild %s)", channel_id, guild_id)
            except discord.Forbidden:
                logger.warning("No permission to send executor alert in channel %s", channel_id)
            except Exception as e:
                logger.warning("Failed to send executor alert to %s: %s", channel_id, e)

    except Exception as e:
        logger.exception("Executor checker error: %s", e)


@tasks.loop(minutes=5)
async def check_roblox_updates():
    try:
        current = await fetch_roblox_version("current")
        previous = load_roblox_cache()

        changed_platforms: list[str] = []
        for platform in ("Windows", "Mac", "Android", "iOS"):
            new_ver = current.get(platform)
            old_ver = previous.get(platform)
            if new_ver and old_ver and str(new_ver) != str(old_ver):
                changed_platforms.append(
                    f"**{platform}** `{old_ver}` → `{new_ver}`"
                )

        # Always save current as new baseline (first run seeds cache with no alert)
        save_roblox_cache({
            "Windows": current.get("Windows"),
            "Mac": current.get("Mac"),
            "Android": current.get("Android"),
            "iOS": current.get("iOS"),
            "WindowsDate": current.get("WindowsDate"),
            "MacDate": current.get("MacDate"),
            "AndroidDate": current.get("AndroidDate"),
            "iOSDate": current.get("iOSDate"),
        })

        if not changed_platforms:
            logger.debug("Roblox checker: no changes")
            return

        logger.info("Roblox version changes: %s", changed_platforms)

        desc = (
            "Roblox has updated. Executors may be down until they update.\n\n"
            + "\n".join(changed_platforms)
        )

        embed = discord.Embed(
            title="Roblox Updated",
            description=desc,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        for platform in ("Windows", "Mac", "Android", "iOS"):
            ver = current.get(platform)
            date = current.get(f"{platform}Date")
            if ver:
                value = f"`{ver}`"
                if date:
                    value += f"\n{date}"
                embed.add_field(name=platform, value=value, inline=True)

        embed.set_footer(text="Automatic checker • weao.xyz • Multi-server")

        targets = get_all_alert_channels("roblox")
        if not targets:
            logger.info("Roblox changes found but no alert channels configured")
            return

        for guild_id, channel_id in targets:
            channel = await _resolve_text_channel(channel_id)
            if channel is None:
                logger.warning("Roblox alert: invalid/missing channel %s (guild %s)", channel_id, guild_id)
                continue
            try:
                await channel.send(embed=embed)
                logger.info("Sent Roblox alert to channel %s (guild %s)", channel_id, guild_id)
            except discord.Forbidden:
                logger.warning("No permission to send Roblox alert in channel %s", channel_id)
            except Exception as e:
                logger.warning("Failed to send Roblox alert to %s: %s", channel_id, e)

    except Exception as e:
        logger.exception("Roblox checker error: %s", e)


@check_executor_updates.before_loop
@check_roblox_updates.before_loop
async def before_checkers():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")

    from commands.prefix.verification import VerifyButton, CaptchaStartView
    bot.add_view(VerifyButton())
    bot.add_view(CaptchaStartView())

    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d application command(s)", len(synced))
    except Exception as e:
        logger.error("Failed to sync application commands: %s", e)

    if not check_executor_updates.is_running():
        check_executor_updates.start()
        logger.info("Executor update checker started")
    if not check_roblox_updates.is_running():
        check_roblox_updates.start()
        logger.info("Roblox update checker started")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"Please wait {error.retry_after:.1f}s before using this command again.",
            delete_after=5,
        )
    elif isinstance(error, commands.CommandNotFound):
        name = ctx.invoked_with
        if name:
            from utils.weao import fetch_executor, build_executor_embed
            exe = await fetch_executor(name)
            if exe:
                embed, view = build_executor_embed(exe)
                await ctx.send(embed=embed, view=view)
    else:
        logger.error("Command error in %s: %s", ctx.command, error)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return

    from commands.prefix.verification import get_guild_config, assign_verified_role

    cfg = get_guild_config(payload.guild_id)
    if not cfg or cfg.get("method") != "reaction":
        return
    if cfg.get("panel_message_id") != payload.message_id:
        return

    emoji = cfg.get("reaction_emoji", "✅")
    if str(payload.emoji) != emoji and getattr(payload.emoji, "name", None) != emoji:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    ok, msg = await assign_verified_role(member, guild)
    try:
        await member.send(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cog loading
# ---------------------------------------------------------------------------

async def load_extensions():
    base = Path(__file__).parent / "commands"
    for category in ("prefix", "slash"):
        folder = base / category
        if not folder.exists():
            continue
        for file in folder.glob("*.py"):
            if file.name.startswith("_"):
                continue
            ext = f"commands.{category}.{file.stem}"
            try:
                await bot.load_extension(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception as e:
                logger.error("Failed to load %s: %s", ext, e)


async def main():
    ensure_data_dir()
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
