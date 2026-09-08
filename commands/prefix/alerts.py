"""
Prefix commands for update alert channel configuration.
Per-guild storage — works on any server the bot is in.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from utils.weao import set_alert_channel, get_alert_channel


class AlertsPrefix(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="execupdatechecker")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def exec_update_checker(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """
        Set the channel for automatic executor update alerts.
        Usage: !execupdatechecker #channel
        Omit channel to disable.
        """
        if channel is None:
            set_alert_channel(ctx.guild.id, "executor", None)
            await ctx.send("Executor update alerts disabled for this server.")
            return

        set_alert_channel(ctx.guild.id, "executor", channel.id)
        await ctx.send(
            f"Executor update alerts will be sent to {channel.mention} "
            f"(this server only — multi-server safe)."
        )

    @commands.command(name="robloxupdatechecker")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def roblox_update_checker(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """
        Set the channel for automatic Roblox update alerts.
        Usage: !robloxupdatechecker #channel
        Omit channel to disable.
        """
        if channel is None:
            set_alert_channel(ctx.guild.id, "roblox", None)
            await ctx.send("Roblox update alerts disabled for this server.")
            return

        set_alert_channel(ctx.guild.id, "roblox", channel.id)
        await ctx.send(
            f"Roblox update alerts will be sent to {channel.mention} "
            f"(this server only — multi-server safe)."
        )

    @commands.command(name="alertstatus")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def alert_status(self, ctx: commands.Context):
        """Show current alert channel configuration for this server."""
        exe_ch = get_alert_channel(ctx.guild.id, "executor")
        rbx_ch = get_alert_channel(ctx.guild.id, "roblox")

        embed = discord.Embed(
            title="Alert Channels (this server)",
            description="Config is stored per-server so the bot works on any guild.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Executor updates",
            value=f"<#{exe_ch}>" if exe_ch else "Not set",
            inline=False,
        )
        embed.add_field(
            name="Roblox updates",
            value=f"<#{rbx_ch}>" if rbx_ch else "Not set",
            inline=False,
        )
        embed.set_footer(text="Checkers run every 5 minutes • !testalert")
        await ctx.send(embed=embed)

    @commands.command(name="testalert")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def test_alert(self, ctx: commands.Context, kind: str = "both"):
        """
        Send a test alert to the configured channel(s).
        Usage: !testalert [executor|roblox|both]
        """
        kind = (kind or "both").lower().strip()
        if kind not in ("executor", "roblox", "both"):
            await ctx.send("Use `executor`, `roblox`, or `both`.")
            return

        sent = []
        if kind in ("executor", "both"):
            ch_id = get_alert_channel(ctx.guild.id, "executor")
            if not ch_id:
                await ctx.send("Executor alert channel is not set. Use `!execupdatechecker #channel` first.")
            else:
                try:
                    channel = ctx.guild.get_channel(ch_id)
                    if channel is None:
                        channel = await self.bot.fetch_channel(ch_id)
                except Exception:
                    channel = None
                if not isinstance(channel, discord.TextChannel):
                    await ctx.send(f"Could not resolve executor channel `{ch_id}`.")
                else:
                    embed = discord.Embed(
                        title="Executor Update Detected (TEST)",
                        description=(
                            "**ExampleExecutor** updated to version `1.0.0`\n"
                            "This is a test — real alerts look like this."
                        ),
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.set_footer(text="Test alert • weao.xyz • Multi-server")
                    await channel.send(embed=embed)
                    sent.append(f"executor → {channel.mention}")

        if kind in ("roblox", "both"):
            ch_id = get_alert_channel(ctx.guild.id, "roblox")
            if not ch_id:
                await ctx.send("Roblox alert channel is not set. Use `!robloxupdatechecker #channel` first.")
            else:
                try:
                    channel = ctx.guild.get_channel(ch_id)
                    if channel is None:
                        channel = await self.bot.fetch_channel(ch_id)
                except Exception:
                    channel = None
                if not isinstance(channel, discord.TextChannel):
                    await ctx.send(f"Could not resolve Roblox channel `{ch_id}`.")
                else:
                    embed = discord.Embed(
                        title="Roblox Updated (TEST)",
                        description=(
                            "Roblox has updated. Executors may be down until they update.\n\n"
                            "**Windows** `old` → `new`\n"
                            "This is a test — real alerts look like this."
                        ),
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.set_footer(text="Test alert • weao.xyz • Multi-server")
                    await channel.send(embed=embed)
                    sent.append(f"roblox → {channel.mention}")

        if sent:
            await ctx.send("Test alert(s) sent: " + ", ".join(sent))

    @exec_update_checker.error
    @roblox_update_checker.error
    @alert_status.error
    @test_alert.error
    async def alerts_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Administrator permission required.")
        else:
            await ctx.send(f"Error: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsPrefix(bot))
