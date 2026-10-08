from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from ..embeds import (
    guide_embed,
    hit_embed,
    search_results_embed,
    status_embed,
)


SearchType = Literal["all", "item", "recipe", "building", "crop", "fishing", "document", "level"]
GuideTopic = Literal["search", "crafting", "building", "farming", "fishing", "maps", "codex"]


class PublicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="search", description="Search the SV13 Survivor Database.")
    @app_commands.describe(query="What are you looking for?", type="Optional database section.")
    async def search(self, interaction: discord.Interaction, query: str, type: SearchType = "all"):
        hits = self.bot.knowledge.search(query, kind=type, limit=8)
        await interaction.response.send_message(embed=search_results_embed(query, hits))

    @app_commands.command(name="item", description="Look up an SV13 item.")
    async def item(self, interaction: discord.Interaction, name: str):
        await self._lookup(interaction, name, "item")

    @item.autocomplete("name")
    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=value, value=value)
            for value in self.bot.knowledge.autocomplete(current, "item")
        ]

    @app_commands.command(name="recipe", description="Look up an SV13 crafting recipe.")
    async def recipe(self, interaction: discord.Interaction, name: str):
        await self._lookup(interaction, name, "recipe")

    @recipe.autocomplete("name")
    async def recipe_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=value, value=value)
            for value in self.bot.knowledge.autocomplete(current, "recipe")
        ]

    @app_commands.command(name="building", description="Look up an SV13 construction definition.")
    async def building(self, interaction: discord.Interaction, name: str):
        await self._lookup(interaction, name, "building")

    @building.autocomplete("name")
    async def building_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=value, value=value)
            for value in self.bot.knowledge.autocomplete(current, "building")
        ]

    @app_commands.command(name="crop", description="Look up an SV13 crop/growing guide.")
    async def crop(self, interaction: discord.Interaction, name: str):
        await self._lookup(interaction, name, "crop")

    @crop.autocomplete("name")
    async def crop_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=value, value=value)
            for value in self.bot.knowledge.autocomplete(current, "crop")
        ]

    @app_commands.command(name="fishing", description="Search SV13 bait and fishing loot.")
    async def fishing(self, interaction: discord.Interaction, name: str):
        hits = self.bot.knowledge.search(name, kind="fishing", limit=1)
        if not hits:
            hits = self.bot.knowledge.search(name, kind="bait", limit=1)
        if not hits:
            await interaction.response.send_message(
                "No public fishing intel matched that search.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=hit_embed(hits[0], self.bot.knowledge, self.bot.config)
        )

    @fishing.autocomplete("name")
    async def fishing_autocomplete(self, interaction: discord.Interaction, current: str):
        values = self.bot.knowledge.autocomplete(current, "fishing")
        values += self.bot.knowledge.autocomplete(current, "bait")
        seen = []
        for value in values:
            if value not in seen:
                seen.append(value)
        return [app_commands.Choice(name=v, value=v) for v in seen[:25]]

    @app_commands.command(name="map", description="Look up SV13 area/map intel.")
    async def map_command(self, interaction: discord.Interaction, name: str):
        await self._lookup(interaction, name, "level")

    @map_command.autocomplete("name")
    async def map_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=value, value=value)
            for value in self.bot.knowledge.autocomplete(current, "level")
        ]

    @app_commands.command(name="codex", description="Search recovered SV13 documents/lore.")
    async def codex(self, interaction: discord.Interaction, name: str):
        await self._lookup(interaction, name, "document")

    @codex.autocomplete("name")
    async def codex_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=value, value=value)
            for value in self.bot.knowledge.autocomplete(current, "document")
        ]

    @app_commands.command(name="guide", description="Open a generalized SV13 field-manual guide.")
    async def guide(self, interaction: discord.Interaction, topic: GuideTopic = "search"):
        await interaction.response.send_message(embed=guide_embed(topic, self.bot.knowledge))

    @app_commands.command(name="sv13status", description="Show the currently loaded SV13 knowledge package.")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=status_embed(self.bot.knowledge))

    async def _lookup(self, interaction: discord.Interaction, query: str, kind: str):
        hit = self.bot.knowledge.best(query, kind=kind)
        if hit is None:
            review = self.bot.knowledge.best(query, kind=kind, include_review=True)
            if review is not None:
                await interaction.response.send_message(
                    "I found a matching entry, but it is currently marked review-only in the Unity knowledge package.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "No public Survivor Database entry matched that search.",
                    ephemeral=True,
                )
            return

        await interaction.response.send_message(
            embed=hit_embed(hit, self.bot.knowledge, self.bot.config)
        )


async def setup(bot):
    await bot.add_cog(PublicCommands(bot))
