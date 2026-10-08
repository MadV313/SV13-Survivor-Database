# SV13 Survivor Database Bot v0.1.0

A Discord bot that consumes the **SV13 Project Intelligence v0.7 knowledge package**.

The Unity project remains the source of truth. The bot reads:

`<Unity Project>\SV13_Knowledge\Latest\manifest.json`

and the accompanying JSON datasets.

## Included commands

Public:

- `/search`
- `/guide`
- `/item`
- `/recipe`
- `/building`
- `/crop`
- `/fishing`
- `/map`
- `/codex`
- `/sv13status`

Admin:

- `/sv13setup` — creates/repairs the SV13 category, two text channels, and four forum channels.
- `/sv13sync` — forces a knowledge reload and posts an intel-update card.
- `/sv13publish` — incrementally creates/updates forum guide posts.

The bot maintains a local SQLite state file so a later Unity export can update existing guide posts instead of creating duplicates.

## Discord structure created by `/sv13setup`

Category:

**SV13 • SURVIVOR DATABASE**

Channels:

- `#database-terminal`
- `#intel-updates`
- `item-index` (Forum)
- `crafting-manual` (Forum)
- `construction-manual` (Forum)
- `field-manual` (Forum)

The forums are bot-managed by default. Members consume them and use slash commands anywhere they can access the bot.

## Windows install

1. Install Python 3.11+.
2. Run `install_windows.bat`.
3. Edit `.env`.
4. Point `SV13_KNOWLEDGE_DIR` at the Unity-generated `SV13_Knowledge\Latest` folder.
5. Run the smoke test before connecting Discord:

```bat
.venv\Scripts\python.exe tools\smoke_test.py --knowledge "C:\Path\To\UnityProject\SV13_Knowledge\Latest"
```

6. Run `run_bot.bat`.

## First Discord test sequence

1. Create the Discord application/bot and invite it to a private test server.
2. Put the bot token and server ID in `.env`.
3. Start the bot.
4. Run `/sv13setup`.
5. Run `/sv13status`.
6. Test `/search cabbage`, `/item Cabbage`, `/recipe .45 ACP`, and `/building SV13_GreenHouse`.
7. Run `/sv13publish scope:recipes limit:20`.
8. Verify posts appeared in `crafting-manual`.
9. Run `/sv13publish scope:buildings limit:20`.
10. Export a fresh knowledge package from Unity, then run `/sv13sync`.
11. After initial publishing is proven, set `AUTO_PUBLISH=true` if desired.

## Knowledge publication policy

The bot ingests the entire package but publicly exposes only:

- `SV13AuthoredCandidate`
- `ProjectIntegratedCandidate`

by default.

Additional conservative filters hide obvious example/demo/prototype data, blank level definitions, and recipes whose ingredients are not confirmed.

This policy lives on the bot side so Unity can continue exporting all evidence without deleting or rewriting source data.

## Website integration

`WEB_BASE_URL` is reserved now. Leave it blank until the site exists.

The website should consume the same versioned knowledge package/manifest as Discord. Once the domain and hosting are ready, the bot can move from a local Unity folder to a hosted knowledge endpoint without changing the user-facing command model.
