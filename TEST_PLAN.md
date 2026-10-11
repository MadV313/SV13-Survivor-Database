# SV13 Bot v0.2.1 Test Plan

## A. Repository preflight

```bat
.venv\Scripts\python.exe tools\repo_audit.py
```

Expected: `PASS`.

## B. Local knowledge test — no Discord token needed

```bat
.venv\Scripts\python.exe tools\smoke_test.py --knowledge "C:\Path\To\Project\SV13_Knowledge\Latest"
```

Expected:

- manifest/file integrity PASS
- package version printed
- item search PASS
- recipe search PASS
- building search PASS
- crop search PASS
- document search PASS
- final loader/search PASS

## C. Discord startup

1. Put the token, server ID and local/remote knowledge source in `.env`.
2. Run `run_bot.bat`.
3. Console should report login, package version, guild count, knowledge source and state DB path.
4. Run `/sv13status`.

## D. Structure / repair

1. `/sv13setup`
2. Confirm the category, two text channels and four forums exist.
3. Run `/sv13setup` again.
4. Confirm it repairs/reuses the existing structure rather than creating duplicates.
5. Confirm each forum now has managed tags and each `START HERE` post carries the `Start Here` tag.

## E. Query checks

- `/search cabbage`
- `/item Cabbage`
- `/recipe .45 ACP`
- `/building SV13_GreenHouse`
- `/crop Cabbage`
- `/codex Didn't Mean to Stay`
- `/guide crafting`

## F. Publisher

1. `/sv13publish scope:recipes limit:20`
2. Confirm recipe posts are created.
3. Run the same command again.
4. Existing unchanged posts should be skipped.
5. Confirm the published recipe/building posts have appropriate forum tags.
6. Change one recipe in Unity, export again, `/sv13sync`, then publish.
7. The existing changed post should be edited rather than duplicated.
8. Replace one existing sprite without changing the JSON record, publish again, and confirm the existing post updates its attachment in place.

## G. Automatic sync

1. Leave `AUTO_PUBLISH=false` for the first live tests.
2. Update the knowledge source.
3. Wait for the sync interval or use `/sv13sync`.
4. Confirm `#intel-updates` receives an uplink card only when hashes/package metadata actually changed.
5. Run `/sv13sync` again without changing the package and confirm the response is private and no second public uplink card is posted.

Only enable `AUTO_PUBLISH=true` after the public content/layout has been reviewed.
