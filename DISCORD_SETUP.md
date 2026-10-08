# Discord Application Setup — SV13 Survivor Database

## Create the application

1. Create a Discord application/bot.
2. Copy the token directly into local `.env` or the deployment secret store.
3. Never commit or paste the token into source control, screenshots, logs or chat.
4. This bot does not require Message Content, Presence, or Server Members privileged intents.

## Invite scopes

Required OAuth scopes:

- `bot`
- `applications.commands`

For the first private-server setup pass, Administrator is the easiest temporary permission because `/sv13setup` creates and repairs channels/forums. After setup is proven, permissions can be reduced.

## Server ID

Enable Discord Developer Mode, copy the server ID, and set:

`DISCORD_GUILD_ID=<server id>`

Guild-scoped command syncing is intentionally supported for fast test iterations.

## Local knowledge

Use:

`SV13_KNOWLEDGE_DIR=C:\...\SV13_Knowledge\Latest`

## Hosted/Railway knowledge

Use:

`SV13_KNOWLEDGE_BASE_URL=https://.../Latest`

The bot downloads the remote manifest/files to its cache and verifies manifest hashes before switching to the new package.

## First Discord sequence

1. Start the bot.
2. `/sv13setup`
3. `/sv13status`
4. `/search cabbage`
5. `/item Cabbage`
6. `/recipe .45 ACP`
7. `/building SV13_GreenHouse`
8. `/sv13publish scope:recipes limit:20`
9. Review the guide layout before enabling `AUTO_PUBLISH`.

## Persistent publication state

SQLite tracks category/channel IDs and generated forum threads. Production hosting must keep `STATE_DB_PATH` on persistent storage.
