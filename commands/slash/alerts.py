"""
Slash commands for update alert channel configuration.
Per-guild storage — works on any server the bot is in.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.weao import set_alert_channel, get_alert_channel


class AlertsSlash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="execupdatechecker", description="Set channel for executor update alerts (this server)")
    @app_commands.describe(channel="Channel to receive alerts (leave empty to disable)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def exec_update_checker(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ):
        if channel is None:
            set_alert_channel(interaction.guild_id, "executor", None)
            await interaction.response.send_message(
                "Executor update alerts disabled for this server.", ephemeral=True
            )
            return

        set_alert_channel(interaction.guild_id, "executor", channel.id)
        await interaction.response.send_message(
            f"Executor update alerts will be sent to {channel.mention} "
            f"(this server only — multi-server safe).",
            ephemeral=True,
        )

    @app_commands.command(name="robloxupdatechecker", description="Set channel for Roblox update alerts (this server)")
    @app_commands.describe(channel="Channel to receive alerts (leave empty to disable)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def roblox_update_checker(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ):
        if channel is None:
            set_alert_channel(interaction.guild_id, "roblox", None)
            await interaction.response.send_message(
                "Roblox update alerts disabled for this server.", ephemeral=True
            )
            return

        set_alert_channel(interaction.guild_id, "roblox", channel.id)
        await interaction.response.send_message(
            f"Roblox update alerts will be sent to {channel.mention} "
            f"(this server only — multi-server safe).",
            ephemeral=True,
        )

    @app_commands.command(name="alertstatus", description="Show alert channels for this server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def alert_status(self, interaction: discord.Interaction):
        exe_ch = get_alert_channel(interaction.guild_id, "executor")
        rbx_ch = get_alert_channel(interaction.guild_id, "roblox")

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
        embed.set_footer(text="Checkers run every 5 minutes • /testalert")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="testalert", description="Send a test alert to configured channels")
    @app_commands.describe(kind="Which alert type to test")
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="both", value="both"),
            app_commands.Choice(name="executor", value="executor"),
            app_commands.Choice(name="roblox", value="roblox"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def test_alert(
        self,
        interaction: discord.Interaction,
        kind: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        k = (kind.value if kind else "both").lower()

        sent = []
        if k in ("executor", "both"):
            ch_id = get_alert_channel(interaction.guild_id, "executor")
            if not ch_id:
                await interaction.followup.send(
                    "Executor alert channel is not set. Use /execupdatechecker first.",
                    ephemeral=True,
                )
            else:
                try:
                    channel = interaction.guild.get_channel(ch_id)
                    if channel is None:
                        channel = await self.bot.fetch_channel(ch_id)
                except Exception:
                    channel = None
                if not isinstance(channel, discord.TextChannel):
                    await interaction.followup.send(
                        f"Could not resolve executor channel `{ch_id}`.", ephemeral=True
                    )
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

        if k in ("roblox", "both"):
            ch_id = get_alert_channel(interaction.guild_id, "roblox")
            if not ch_id:
                await interaction.followup.send(
                    "Roblox alert channel is not set. Use /robloxupdatechecker first.",
                    ephemeral=True,
                )
            else:
                try:
                    channel = interaction.guild.get_channel(ch_id)
                    if channel is None:
                        channel = await self.bot.fetch_channel(ch_id)
                except Exception:
                    channel = None
                if not isinstance(channel, discord.TextChannel):
                    await interaction.followup.send(
                        f"Could not resolve Roblox channel `{ch_id}`.", ephemeral=True
                    )
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
            await interaction.followup.send(
                "Test alert(s) sent: " + ", ".join(sent), ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsSlash(bot))
