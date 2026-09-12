#!/usr/bin/env python3
"""Build data/stats.json for the Dragonfyre scoreboard.

Emits player NAMES and numbers only. Never emits UUIDs, the server address,
the Tailscale IP, or the invite link.
"""
import json, os, glob, datetime, re

SRV  = os.path.expanduser("~/dragonfyre-server/unpacked")
SITE = os.path.expanduser("~/dragonfyre-site")
OUT  = os.path.join(SITE, "data", "stats.json")
TICK = 20.0
INT_MAX = 2147483647
MIN_RANKED_HOURS = 2.0

WEIGHTS = {"threat": .40, "conquest": .25, "survival": .20, "frontier": .10, "craft": .05}

# Derived from the pack's own L2Hostility `min` floors per boss.
BOSS_POINTS = [
    (150, ["minecraft:ender_dragon", "alexsmobs:void_worm", "cisco_mod:descended_cisco",
           "block_factorys_bosses:infernal_dragon"]),
    (125, ["minecraft:warden", "cisco_mod:fellkingboss", "alexsmobs:warped_mosco"]),
    (100, ["bosses_of_mass_destruction:gauntlet", "bosses_of_mass_destruction:lich",
           "bosses_of_mass_destruction:obsidilith", "legendary_monsters:ancient_guardian",
           "legendary_monsters:cloud_golem", "legendary_monsters:endersent",
           "legendary_monsters:frostbitten_golem", "legendary_monsters:overgrown_colossus",
           "legendary_monsters:posessed_paladin", "legendary_monsters:shulker_mimic",
           "legendary_monsters:withered_abomination", "block_factorys_bosses:sandworm",
           "block_factorys_bosses:underworld_knight"]),
    (75,  ["minecraft:wither", "cisco_mod:cisco", "block_factorys_bosses:yeti",
           "legendary_monsters:lava_eater", "legendary_monsters:warped_fungussus",
           "legendary_monsters:skeletosaurus", "bosses_of_mass_destruction:void_blossom",
           "aquamirae:captain_cornelia"]),
    (25,  ["iceandfire:fire_dragon", "iceandfire:ice_dragon", "iceandfire:lightning_dragon",
           "mutantmonsters:mutant_zombie", "mutantmonsters:mutant_skeleton",
           "mutantmonsters:mutant_creeper", "mutantmonsters:mutant_enderman",
           "cataclysm:netherite_monstrosity", "cataclysm:ender_guardian",
           "cataclysm:ignis", "cataclysm:harbinger", "cataclysm:leviathan",
           "cataclysm:ancient_remnant", "mowziesmobs:frostmaw", "mowziesmobs:wroughtnaut"]),
]
KILL_POINTS = {e: p for p, ents in BOSS_POINTS for e in ents}

def kill_value(entity):
    return KILL_POINTS.get(entity, 1)

def names():
    out = {}
    try:
        for e in json.load(open(os.path.join(SRV, "usercache.json"))):
            out[e["uuid"]] = e["name"]
    except Exception:
        pass
    return out

def nbt_extra(uuid):
    """Pull L2Hostility level, dimensions and Origin from playerdata."""
    blank = {"level": 0, "dims": 0, "rank": 0, "origin": None, "blessing": None, "clazz": None}
    p = os.path.join(SRV, "world", "playerdata", uuid + ".dat")
    if not os.path.exists(p): return blank
    try:
        import nbtlib
        root = nbtlib.load(p)
        root = root if hasattr(root, "keys") else root.root
    except Exception:
        return blank

    def find(n, key, depth=0):
        if depth > 40: return None
        try: items = list(n.items())
        except Exception:
            if isinstance(n, list):
                for v in n:
                    r = find(v, key, depth + 1)
                    if r is not None: return r
            return None
        if key in n: return n[key]
        for _, v in items:
            r = find(v, key, depth + 1)
            if r is not None: return r
        return None

    def blocks(n, want, hits=None, depth=0):
        if hits is None: hits = []
        if depth > 40: return hits
        try: items = list(n.items())
        except Exception:
            if isinstance(n, list):
                for v in n: blocks(v, want, hits, depth + 1)
            return hits
        if all(k in n for k in want): hits.append(n)
        for _, v in items: blocks(v, want, hits, depth + 1)
        return hits

    o = dict(blank)
    hs = blocks(root, ["difficulty", "dimensions", "maxRankKilled"])
    if hs:
        h = hs[0]
        d = h.get("difficulty") or {}
        try: o["level"] = int(d.get("level", 0)) + int(d.get("extraLevel", 0))
        except Exception: pass
        try: o["dims"] = max(0, len(list(h.get("dimensions") or [])) - 1)
        except Exception: pass
        try: o["rank"] = int(h.get("maxRankKilled", 0))
        except Exception: pass
    layers = find(root, "Origins")
    if layers is not None:
        try:
            o["origin"]   = str(layers.get("origins:origin") or "") or None
            o["blessing"] = str(layers.get("cisco_rpg_origins:divineblessings") or "") or None
            o["clazz"]    = str(layers.get("origins-classes:class") or "") or None
        except Exception: pass
    return o

def pretty(rid):
    if not rid: return None
    return rid.split(":")[-1].replace("_", " ").title()

def collect():
    nm = names()
    players = []
    for f in glob.glob(os.path.join(SRV, "world/stats/*.json")):
        uuid = os.path.basename(f)[:-5]
        name = nm.get(uuid)
        if not name: continue
        try: st = json.load(open(f)).get("stats", {})
        except Exception: continue
        c   = st.get("minecraft:custom", {})
        kil = st.get("minecraft:killed", {})
        kby = st.get("minecraft:killed_by", {})
        mnd = st.get("minecraft:mined", {})
        crf = st.get("minecraft:crafted", {})
        x   = nbt_extra(uuid)

        ticks = c.get("minecraft:play_time", 0)
        hours = ticks / TICK / 3600
        deaths = c.get("minecraft:deaths", 0)
        conquest = sum(kill_value(e) * n for e, n in kil.items())
        bosses = sum(n for e, n in kil.items() if e in KILL_POINTS)
        dist = (c.get("minecraft:walk_one_cm", 0) + c.get("minecraft:sprint_one_cm", 0)
                + c.get("minecraft:fly_one_cm", 0) + c.get("minecraft:boat_one_cm", 0)
                + c.get("minecraft:horse_one_cm", 0) + c.get("minecraft:swim_one_cm", 0))
        dmg_taken = c.get("minecraft:damage_taken", 0)
        worst = max(kby.items(), key=lambda kv: kv[1])[0] if kby else None

        players.append({
            "name": name,
            "hours": round(hours, 2),
            "level": x["level"], "dims": x["dims"], "rank": x["rank"],
            "origin": pretty(x["origin"]), "blessing": pretty(x["blessing"]),
            "clazz": pretty(x.get("clazz")),
            "deaths": deaths,
            "mob_kills": sum(kil.values()),
            "boss_kills": bosses,
            "conquest_raw": conquest,
            "distance_km": round(dist / 100000, 2),
            "mined": sum(mnd.values()),
            "crafted": sum(crf.values()),
            "streak_h": round(c.get("minecraft:time_since_death", 0) / TICK / 3600, 1),
            "dmg_dealt": c.get("minecraft:damage_dealt", 0),
            "dmg_taken_overflow": dmg_taken >= INT_MAX,
            "top_killer": pretty(worst),
            "top_mobs": sorted(((pretty(k), v) for k, v in kil.items()),
                               key=lambda kv: -kv[1])[:5],
        })
    return players

def score(players):
    if not players: return players
    def norm(vals):
        m = max(vals) if vals else 0
        return [(v / m if m > 0 else 0.0) for v in vals]

    threat   = norm([p["level"] for p in players])
    conquest = norm([p["conquest_raw"] for p in players])
    # survival: deaths per hour, inverted (fewer is better), plus streak
    dph = [(p["deaths"] / p["hours"]) if p["hours"] >= 0.1 else 0.0 for p in players]
    worst_dph = max(dph) if dph else 0
    surv_base = [(1 - (d / worst_dph)) if worst_dph > 0 else 1.0 for d in dph]
    streak = norm([p["streak_h"] for p in players])
    survival = [0.7 * a + 0.3 * b for a, b in zip(surv_base, streak)]
    frontier = [0.6 * a + 0.4 * b for a, b in
                zip(norm([p["dims"] for p in players]),
                    norm([p["distance_km"] for p in players]))]
    craft = [0.5 * a + 0.5 * b for a, b in
             zip(norm([p["mined"] for p in players]),
                 norm([p["crafted"] for p in players]))]

    for i, p in enumerate(players):
        parts = {"threat": threat[i], "conquest": conquest[i], "survival": survival[i],
                 "frontier": frontier[i], "craft": craft[i]}
        p["parts"] = {k: round(v * 100, 1) for k, v in parts.items()}
        p["score"] = round(sum(WEIGHTS[k] * v for k, v in parts.items()) * 100, 1)
        p["ranked"] = p["hours"] >= MIN_RANKED_HOURS
    players.sort(key=lambda p: (p["ranked"], p["score"]), reverse=True)
    for i, p in enumerate(players):
        p["rank_pos"] = i + 1 if p["ranked"] else None
    return players

def main():
    players = score(collect())
    doc = {
        "generated": datetime.datetime.now(datetime.timezone.utc)
                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "weights": WEIGHTS,
        "min_ranked_hours": MIN_RANKED_HOURS,
        "totals": {
            "players": len(players),
            "hours": round(sum(p["hours"] for p in players), 1),
            "mob_kills": sum(p["mob_kills"] for p in players),
            "boss_kills": sum(p["boss_kills"] for p in players),
            "deaths": sum(p["deaths"] for p in players),
        },
        "players": players,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w"), indent=1)

    # Safety net. Deliberately pattern-based: this file is public, so it must not
    # contain the very values it is guarding against.
    blob = open(OUT).read()
    FORBIDDEN = [
        (r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b",
         "a private mesh (CGNAT 100.64/10) address"),
        (r"\b[\w-]+\.ts\.net\b", "a tailnet hostname"),
        (r"tailscale\.com/admin/invite", "a network invite link"),
        (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "a player UUID"),
    ]
    for pattern, what in FORBIDDEN:
        m = re.search(pattern, blob)
        assert not m, f"REFUSING TO WRITE: output contains {what} ({m.group(0)})"
    print(f"wrote {OUT} ({len(players)} players, {len(blob)} bytes)")

if __name__ == "__main__":
    main()
