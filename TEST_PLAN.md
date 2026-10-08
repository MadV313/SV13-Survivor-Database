# SV13 Bot v0.1.0 Test Plan

## A. Local knowledge test — no Discord token needed

After `install_windows.bat`:

```bat
.venv\Scripts\python.exe tools\smoke_test.py --knowledge "C:\Path\To\Project\SV13_Knowledge\Latest"
```

Expected:

- package version printed
- item search PASS
- recipe search PASS
- building search PASS
- crop search PASS
- document search PASS
- final line: `Knowledge loader/search smoke test PASSED.`

## B. Discord startup

1. Put token, server ID and knowledge path in `.env`.
2. Run `run_bot.bat`.
3. Console should report the bot logged in and slash commands synced.
4. Run `/sv13status`.

## C. Query checks

Test:

- `/search cabbage`
- `/item Cabbage`
- `/recipe .45 ACP`
- `/building SV13_GreenHouse`
- `/crop Cabbage`
- `/codex Didn't Mean to Stay`
- `/guide crafting`

## D. Structure/publisher

1. `/sv13setup`
2. Confirm category/channels/forums appear.
3. `/sv13publish scope:recipes limit:20`
4. Confirm recipe forum posts are created.
5. Run the same command again.
6. Existing unchanged posts should be skipped rather than duplicated.

## E. Unity → Discord sync

1. Leave the bot running.
2. Make a harmless test change in Unity data.
3. Build a fresh **Authoritative Knowledge Package**.
4. Wait for the configured sync interval, or run `/sv13sync`.
5. `#intel-updates` should receive an uplink update.
6. Run `/sv13publish` for the relevant scope.
7. The existing changed forum post should be edited rather than duplicated.

Only after these tests pass should `AUTO_PUBLISH=true` be enabled.
