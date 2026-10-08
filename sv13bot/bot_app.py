from __future__ import annotations

import asyncio
import logging
from typing import List

import discord
from discord.ext import commands, tasks

from .config import BotConfig
from .discord_setup import ensure_discord_structure, get_configured_channel
from .embeds import sync_embed
from .knowledge import KnowledgeStore
from .publisher import KnowledgePublisher
from .state import StateStore


log = logging.getLogger("sv13bot")


class SV13Bot(commands.Bot):
    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.config = config
        self.knowledge = KnowledgeStore(config.knowledge_dir, config.public_statuses)
        self.knowledge.load()
        self.state = StateStore(config.state_db_path)
        self.publisher = KnowledgePublisher(config, self.knowledge, self.state)

        self.knowledge_sync_loop.change_interval(
            seconds=float(config.sync_interval_seconds)
        )

    async def setup_hook(self) -> None:
        await self.load_extension("sv13bot.cogs.public")
        await self.load_extension("sv13bot.cogs.admin")

        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %s commands to guild %s", len(synced), self.config.guild_id)
        else:
            synced = await self.tree.sync()
            log.info("Synced %s global commands", len(synced))

        if self.config.auto_sync and not self.knowledge_sync_loop.is_running():
            self.knowledge_sync_loop.start()

    async def on_ready(self) -> None:
        log.info(
            "Logged in as %s | package=%s | guilds=%s",
            self.user,
            self.knowledge.package_version,
            len(self.guilds),
        )

        if self.config.auto_setup:
            for guild in self._target_guilds():
                try:
                    await ensure_discord_structure(guild, self.config, self.state)
                except Exception:
                    log.exception("Automatic Discord setup failed for guild %s", guild.id)

    def _target_guilds(self) -> List[discord.Guild]:
        if self.config.guild_id:
            guild = self.get_guild(self.config.guild_id)
            return [guild] if guild is not None else []
        return list(self.guilds)

    async def post_sync_update(
        self, guild: discord.Guild, changed_files: List[str]
    ) -> None:
        channel = await get_configured_channel(guild, self.state, "intel")
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=sync_embed(self.knowledge, changed_files))
            except discord.HTTPException:
                log.exception("Could not post SV13 intel update in guild %s", guild.id)

    @tasks.loop(minutes=5.0)
    async def knowledge_sync_loop(self) -> None:
        try:
            changed, changed_files = await asyncio.to_thread(
                self.knowledge.reload_if_changed, False
            )
            if not changed:
                return

            log.info(
                "SV13 knowledge package changed: %s (%s)",
                self.knowledge.package_version,
                ", ".join(changed_files),
            )

            for guild in self._target_guilds():
                await self.post_sync_update(guild, changed_files)

                if self.config.auto_publish:
                    try:
                        result = await self.publisher.publish_changed(
                            guild,
                            scope="all",
                            limit=self.config.auto_publish_batch_size,
                        )
                        log.info(
                            "Auto-publish guild=%s created=%s updated=%s unchanged=%s skipped=%s",
                            guild.id,
                            result["created"],
                            result["updated"],
                            result["unchanged"],
                            result["skipped"],
                        )
                    except Exception:
                        log.exception("Auto-publish failed for guild %s", guild.id)
        except FileNotFoundError:
            log.warning(
                "SV13 knowledge package is not currently available at %s",
                self.config.knowledge_dir,
            )
        except Exception:
            log.exception("SV13 knowledge sync loop failed")

    @knowledge_sync_loop.before_loop
    async def before_knowledge_sync(self) -> None:
        await self.wait_until_ready()


def run() -> None:
    config = BotConfig.load(require_token=True)

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = SV13Bot(config)
    bot.run(config.token, log_handler=None)
