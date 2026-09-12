# Dragonfyre Scoreboard

Live player rankings for a private Minecraft server running
**Cisco's Fantasy Medieval RPG [Dragonfyre]** (1.20.1, Forge 47.4.13).

## The Peril Score

Ranks danger survived, not hours logged.

| Component | Weight | Measures |
|---|---|---|
| Threat | 40% | L2Hostility personal difficulty level |
| Conquest | 25% | Kills weighted by how dangerous the mob is |
| Survival | 20% | Deaths per hour (inverted) + current death-free streak |
| Frontier | 10% | Dimensions visited + distance travelled |
| Craft | 5% | Blocks mined + items crafted (capped) |

Each component is scaled against the current best player, then weighted.
A minimum of 2 hours played is required to be ranked.

## Updating

`tools/build_data.py` reads the server's own stats and playerdata files and
writes `data/stats.json`. It emits player names and numbers only — never
UUIDs, and never the server address.

```bash
tools/.venv/bin/python tools/build_data.py
```

Pushing to `main` triggers a Vercel deploy.
