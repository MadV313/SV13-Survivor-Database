from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from ..discord_setup import ensure_discord_structure
from ..embeds import sync_embed


PublishScope = Literal["all", "items", "recipes", "buildings", "field"]


class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _allowed(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        if self.bot.config.owner_user_id and user.id == self.bot.config.owner_user_id:
            return True
        if isinstance(user, discord.Member) and user.guild_permissions.manage_guild:
            return True
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Manage Server permission is required for that command.",
                ephemeral=True,
            )
        return False

    @app_commands.command(name="sv13setup", description="Create/repair the SV13 bot category and channels.")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_channels(self, interaction: discord.Interaction):
        if not await self._allowed(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside the SV13 server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        channels = await ensure_discord_structure(
            interaction.guild, self.bot.config, self.bot.state
        )
        await interaction.followup.send(
            "SV13 Survivor Database structure is ready:\n"
            + "\n".join(f"• {key}: <#{channel.id}>" for key, channel in channels.items()),
            ephemeral=True,
        )

    @app_commands.command(name="sv13sync", description="Force-reload the Unity knowledge package.")
    @app_commands.default_permissions(manage_guild=True)
    async def sync(self, interaction: discord.Interaction):
        if not await self._allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        changed, changed_files = self.bot.knowledge.reload_if_changed(force=True)
        if interaction.guild is not None:
            await self.bot.post_sync_update(interaction.guild, changed_files)

        await interaction.followup.send(
            f"Loaded package `{self.bot.knowledge.package_version}`. "
            f"Changed/forced datasets: {', '.join(changed_files) if changed_files else 'none detected'}.",
            ephemeral=True,
        )

    @app_commands.command(name="sv13publish", description="Publish/update Unity-backed guide posts.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        scope="Which guide section to publish.",
        limit="Maximum new/updated forum posts this run (1–100).",
    )
    async def publish(
        self,
        interaction: discord.Interaction,
        scope: PublishScope = "all",
        limit: app_commands.Range[int, 1, 100] = 50,
    ):
        if not await self._allowed(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside the SV13 server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await ensure_discord_structure(interaction.guild, self.bot.config, self.bot.state)
        result = await self.bot.publisher.publish_changed(
            interaction.guild,
            scope=scope,
            limit=int(limit),
        )
        await interaction.followup.send(
            "SV13 publication pass complete.\n"
            f"Created: **{result['created']}**\n"
            f"Updated: **{result['updated']}**\n"
            f"Already current: **{result['unchanged']}**\n"
            f"Skipped: **{result['skipped']}**\n\n"
            "Run `/sv13publish` again if more unpublished records remain.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
