# SV13 Survivor Database Bot v0.1.2

Discord bot for the **SV13 Project Intelligence v0.7 knowledge package**.

Unity remains the source of truth. The bot supports two knowledge-source modes:

1. **Local mode** — reads a Unity-generated `SV13_Knowledge/Latest` directory.
2. **Remote mode** — downloads `manifest.json` and its listed files from a hosted HTTP/HTTPS directory into a verified local cache. This is the intended Railway/website path.

## Public commands

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

## Staff commands

- `/sv13setup` — creates/repairs the SV13 category, text channels and guide forums.
- `/sv13sync` — refreshes the configured local/remote knowledge package.
- `/sv13publish` — incrementally creates/updates forum guide posts.

Staff commands perform their own `Manage Server`/owner check; Discord's default command permission alone is not treated as security.

## Discord structure

`/sv13setup` creates or repairs:

- **SV13 • SURVIVOR DATABASE**
  - `#database-terminal`
  - `#intel-updates`
  - `item-index` (Forum)
  - `crafting-manual` (Forum)
  - `construction-manual` (Forum)
  - `field-manual` (Forum)

Existing bot-managed channels are tracked by ID in SQLite and repaired in place where possible.

## Local Windows install

1. Install Python 3.11+.
2. Run `install_windows.bat`.
3. Edit `.env`.
4. Set:
   - `DISCORD_TOKEN`
   - `DISCORD_GUILD_ID`
   - local `SV13_KNOWLEDGE_DIR`
5. Validate the knowledge package:

   ```bat
   .venv\Scripts\python.exe tools\smoke_test.py --knowledge "C:\Path\To\UnityProject\SV13_Knowledge\Latest"
   ```

6. Run `run_bot.bat`.

## Knowledge integrity

On every package load the bot verifies:

- `manifest.json` contains every required dataset
- every manifest-listed file exists
- byte counts match when supplied
- SHA-256 hashes match when supplied
- expected datasets have the correct top-level JSON shape

A broken/partial package is rejected rather than silently replacing the last working data in memory.

## Remote knowledge mode

Set:

```env
SV13_KNOWLEDGE_BASE_URL=https://example.com/sv13-knowledge/Latest
SV13_KNOWLEDGE_CACHE_DIR=data/knowledge-cache
```

The URL must expose:

`manifest.json`, `items.json`, `recipes.json`, `item_categories.json`,
`buildables.json`, `build_materials.json`, `crops.json`, `fishing.json`,
`documents.json`, `levels.json`, `loot_tables.json`, `validation.json`,
and any additional files listed by the manifest.

Downloads are staged and hash-verified before the active cache is replaced.

## Runtime state / Railway warning

The bot stores Discord channel IDs and published-post IDs in SQLite. This file **must persist** in production or the bot can lose track of existing generated posts.

Locally the default is:

`data/sv13_bot.sqlite3`

On Railway, attach a persistent Volume and set `STATE_DB_PATH` inside that mount (we will configure this during the Railway setup pass).

## Publication policy

`AUTO_PUBLISH=false` remains the safe default.

The Unity `contentStatus` value is a source/review classification, not proof of gameplay reachability. Do not enable automatic bulk publishing until the public dataset/layout has been reviewed in Discord.

## Repository preflight

Run:

```bat
.venv\Scripts\python.exe tools\repo_audit.py
```

This checks required files, Python syntax, cache artifacts and obvious committed-secret patterns.

## Website integration

`WEB_BASE_URL` is reserved for the web field manual.

Discord and the website should both consume the same versioned SV13 knowledge package so Unity remains the single source of truth.


## Railway build pin

`runtime.txt` pins Python 3.13.15 and `requirements.txt` pins exact dependency
versions so the first Railway deployment is deterministic.

Railway still requires a reachable knowledge source before the bot can start:
prefer `SV13_KNOWLEDGE_BASE_URL` pointing at the hosted
`SV13_Knowledge/Latest` package.
