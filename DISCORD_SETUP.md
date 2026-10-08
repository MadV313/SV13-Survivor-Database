# Discord Application Setup — SV13 Survivor Database

## 1. Create the application

1. Open the Discord Developer Portal.
2. Create a **New Application** named something like:
   **SV13 Survivor Database**
3. Open the **Bot** section.
4. Set the bot username/icon if desired.
5. Generate/reset the bot token and copy it directly into your local `.env`.

**Do not post the token in Discord, screenshots, GitHub, or ChatGPT.**

This first version does not require Message Content, Presence, or Server Members privileged intents.

## 2. Invite the bot

For the first private-server test, the simplest route is to give the bot **Administrator** temporarily.

Invite it with both scopes:

- `bot`
- `applications.commands`

After the setup/publisher is proven, permissions can be reduced to the exact channel/thread permissions the bot uses.

## 3. Get the server ID

1. Discord User Settings → Advanced → enable **Developer Mode**.
2. Right-click the SV13 test server.
3. Choose **Copy Server ID**.
4. Put that number into `DISCORD_GUILD_ID` in `.env`.

Using a guild ID makes slash-command changes appear in the test server quickly.

## 4. Point the bot at Unity

Unity v0.7 writes a stable folder:

`<Unity Project>\SV13_Knowledge\Latest`

Put that full Windows path into:

`SV13_KNOWLEDGE_DIR=...`

The bot never modifies this folder. It only reads the JSON files and `manifest.json`.

## 5. First server wiring

Start the bot, then run:

`/sv13setup`

The bot creates:

- Category: `SV13 • SURVIVOR DATABASE`
- `#database-terminal`
- `#intel-updates`
- `item-index` forum
- `crafting-manual` forum
- `construction-manual` forum
- `field-manual` forum

The forums are bot-managed by default.

## 6. Initial publication

Do not publish all items at once until the layout is approved.

Start with:

`/sv13publish scope:recipes limit:20`

Then:

`/sv13publish scope:buildings limit:20`

If those look right, continue with more batches. Publication state is saved in SQLite, so rerunning the command updates changed posts and skips unchanged ones.
