"""
PCGamingWiki Game Save Location Scraper v3
Fixes: Handles Steam/Windows/MS Store paths, {{P|game}}, case-insensitive templates
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import date

API_URL = "https://www.pcgamingwiki.com/w/api.php"
OUTPUT_FILE = "gamesaves.json"

# {{p|...}} / {{P|...}} → Location mapping
P_VARS = {
    "userprofile\\documents": "documents",
    "userprofile/documents": "documents",
    "userprofile\\my documents": "documents",
    "localappdata": "appdata_local",
    "appdata": "appdata_roaming",
    "locallow": "appdata_locallow",
    "userprofile\\appdata\\local": "appdata_local",
    "userprofile\\appdata\\roaming": "appdata_roaming",
    "userprofile\\appdata\\locallow": "appdata_locallow",
    "userprofile\\saved games": "documents",
}

POPULAR_GAMES = [
    "Elden Ring", "Baldur's Gate 3", "Cyberpunk 2077", "Starfield",
    "Hogwarts Legacy", "Palworld", "Lethal Company", "Helldivers 2",
    "Dragon's Dogma 2", "Lies of P", "Alan Wake 2", "Remnant II",
    "Armored Core VI: Fires of Rubicon", "Resident Evil 4 (2023)",
    "Dead Space (2023)", "Hi-Fi Rush", "Wo Long: Fallen Dynasty",
    "The Last of Us Part I", "Returnal", "God of War Ragnarök",
    "Marvel's Spider-Man Remastered", "Marvel's Spider-Man: Miles Morales",
    "Horizon Zero Dawn", "Horizon Forbidden West", "Death Stranding",
    "Red Dead Redemption 2", "Grand Theft Auto V",
    "The Witcher 3: Wild Hunt", "Cyberpunk 2077",
    "The Elder Scrolls V: Skyrim", "The Elder Scrolls V: Skyrim Special Edition",
    "Fallout 4", "Fallout: New Vegas", "Fallout 3", "Starfield",
    "Dark Souls III", "Dark Souls II: Scholar of the First Sin", "Dark Souls: Remastered",
    "Sekiro: Shadows Die Twice",
    "Minecraft", "Terraria", "Stardew Valley", "Valheim",
    "Subnautica", "Subnautica: Below Zero", "No Man's Sky",
    "Hades", "Hades II", "Hollow Knight", "Celeste", "Cuphead",
    "Dead Cells", "Ori and the Blind Forest: Definitive Edition",
    "Ori and the Will of the Wisps",
    "Disco Elysium", "Divinity: Original Sin 2",
    "Cities: Skylines", "Cities: Skylines II",
    "Sid Meier's Civilization VI", "Sid Meier's Civilization V",
    "Crusader Kings III", "Europa Universalis IV", "Hearts of Iron IV",
    "Stellaris", "Victoria 3", "Total War: Warhammer III",
    "RimWorld", "Factorio", "Satisfactory", "Oxygen Not Included",
    "Anno 1800", "Age of Empires IV",
    "Age of Empires II: Definitive Edition",
    "Mount & Blade II: Bannerlord", "Kingdom Come: Deliverance",
    "The Sims 4", "Planet Zoo", "Planet Coaster",
    "Euro Truck Simulator 2", "American Truck Simulator",
    "Farming Simulator 22", "Farming Simulator 25",
    "Forza Horizon 5", "Forza Horizon 4",
    "Resident Evil Village", "Resident Evil 2 (2019)",
    "Monster Hunter: World", "Monster Hunter Rise",
    "Assassin's Creed Valhalla", "Assassin's Creed Odyssey",
    "Assassin's Creed Origins", "Assassin's Creed Mirage",
    "Far Cry 6", "Far Cry 5", "Watch Dogs: Legion",
    "Mass Effect Legendary Edition", "Dragon Age: Inquisition",
    "Borderlands 3", "Borderlands 2",
    "Doom Eternal", "Doom (2016)",
    "Control", "Alan Wake Remastered", "Quantum Break",
    "Dying Light 2: Stay Human", "Dying Light",
    "The Forest", "Sons of the Forest",
    "Deep Rock Galactic", "Sea of Thieves", "Grounded",
    "It Takes Two",
    "Persona 5 Royal", "Persona 4 Golden", "Persona 3 Reload",
    "Final Fantasy VII Remake Intergrade", "Final Fantasy XVI",
    "NieR: Automata",
    "Metal Gear Solid V: The Phantom Pain",
    "Devil May Cry 5",
    "Phasmophobia", "Among Us",
    "Rocket League", "Apex Legends",
    "Path of Exile", "Diablo IV", "Diablo III",
    "Football Manager 2024", "Football Manager 2025",
    "Outer Wilds", "Inscryption", "Slay the Spire",
    "Darkest Dungeon", "Darkest Dungeon II",
    "Into the Breach", "FTL: Faster Than Light",
    "Total War: Three Kingdoms",
    "Prison Architect", "Frostpunk", "Frostpunk 2",
    "Tropico 6", "Two Point Hospital",
    "Pillars of Eternity II: Deadfire",
    "Pathfinder: Wrath of the Righteous",
    "Wasteland 3", "XCOM 2",
    "Vampire Survivors", "Dave the Diver", "Tunic",
    "Ready or Not", "Arma 3",
    "Kenshi", "Dwarf Fortress",
    "Manor Lords", "Against the Storm",
    "Enshrouded", "V Rising",
    "Like a Dragon: Infinite Wealth",
    "Star Wars Jedi: Survivor", "Star Wars Jedi: Fallen Order",
    "Titanfall 2",
    "Hitman: World of Assassination",
    "Sniper Elite 5", "Sniper Elite 4",
    "Prey (2017)", "Dishonored 2", "Deathloop",
    "System Shock (2023)", "Black Myth: Wukong",
    "Wuthering Waves", "Genshin Impact",
    "The Talos Principle 2", "Portal 2",
    "Half-Life 2", "Half-Life: Alyx",
    "Psychonauts 2", "A Plague Tale: Requiem",
    "Sifu", "Trek to Yomi",
    "Uncharted: Legacy of Thieves Collection",
    "Nioh 2", "Nioh",
    "The Surge 2", "Lords of the Fallen (2023)",
    "Mortal Kombat 1", "Street Fighter 6",
    "Tekken 8", "Guilty Gear -Strive-",
    "Palworld", "Enshrouded", "Nightingale",
    "Skull and Bones", "Banishers: Ghosts of New Eden",
]
ICONS = {
    "rpg": "⚔️", "action": "🎮", "shooter": "🔫", "strategy": "🏰",
    "simulation": "🚜", "racing": "🏎️", "horror": "👻", "survival": "🌲",
    "puzzle": "🧩", "platform": "🍄", "adventure": "🗺️", "sport": "⚽",
    "sandbox": "⛏️", "souls": "🔥", "dragon": "🐉", "space": "🚀",
    "war": "🪖", "truck": "🚛", "farm": "🚜", "city": "🏙️", "craft": "⛏️",
}


def api_req(params):
    params["format"] = "json"
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "BackupPro/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None


def get_save_wikitext(title):
    """Holt den gesamten Game-data-Abschnitt und sucht nach Save-Daten."""
    # Erst alle Sections holen
    data = api_req({"action": "parse", "page": title, "prop": "sections"})
    if not data or "parse" not in data:
        return None

    # "Game data" Hauptsection finden (enthält config + save subsections)
    game_data_idx = None
    save_idx = None
    for s in data["parse"].get("sections", []):
        line = s.get("line", "").lower()
        idx = s.get("index", "")
        if not idx:
            continue
        if "save" in line and ("game" in line or "data" in line or "location" in line):
            save_idx = idx
            break
        if line == "game data":
            game_data_idx = idx

    target = save_idx or game_data_idx
    if not target:
        return None

    # Section-Inhalt holen
    data2 = api_req({
        "action": "query", "titles": title,
        "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "rvsection": target
    })
    if not data2 or "query" not in data2:
        return None

    for page in data2["query"].get("pages", {}).values():
        revs = page.get("revisions", [])
        if revs:
            text = revs[0].get("slots", {}).get("main", {}).get("*", "")
            # Wenn wir "game data" geholt haben, ist save ein Unterabschnitt
            if "Game data/saves" in text or "Game data/save" in text:
                return text
    return None


def parse_paths(wikitext, game_name):
    """Extrahiert ALLE Save-Pfade aus dem Wikitext."""
    if not wikitext:
        return None

    # Finde alle {{Game data/saves|PLATFORM|PATH}} Einträge
    # Case-insensitive, mit verschachtelten {{...}}
    results = []

    # Alle Zeilen mit Game data/saves durchgehen
    for line in wikitext.split("\n"):
        if "Game data/saves" not in line and "Game data/save" not in line:
            continue

        # Platform erkennen (Windows, Steam, Microsoft Store, etc.)
        platform_match = re.search(r'Game data/saves?\|([^|]+)\|', line, re.IGNORECASE)
        if not platform_match:
            continue
        platform = platform_match.group(1).strip()

        # Nur Windows-kompatible Plattformen
        if platform.lower() not in ("windows", "steam", "microsoft store",
                                      "epic games store", "gog.com", "ubisoft connect"):
            continue

        # Pfad extrahieren - alles nach dem zweiten |
        path_part = line.split("|", 2)
        if len(path_part) < 3:
            continue
        raw_path = path_part[2].rstrip("}").strip()

        # {{p|...}} oder {{P|...}} auflösen
        p_match = re.search(r'\{\{[pP]\|([^}]+)\}\}(.*?)(?:\}\}|$)', raw_path)
        if not p_match:
            continue

        p_var = p_match.group(1).strip().lower().replace("/", "\\")
        remainder = p_match.group(2).strip().rstrip("}").strip("\\ /")

        # Skip {{p|uid}}, {{p|steam}}, {{p|game}} ohne echten Pfad
        if p_var in ("uid", "steam"):
            continue

        # {{P|game}} = Steam-Installationsordner - ignorieren (nicht user-spezifisch)
        if p_var == "game":
            continue

        # Location bestimmen
        location = P_VARS.get(p_var)
        if not location:
            if "document" in p_var:
                location = "documents"
            elif "localappdata" in p_var or "local" == p_var:
                location = "appdata_local"
            elif "locallow" in p_var:
                location = "appdata_locallow"
            elif "appdata" in p_var:
                location = "appdata_roaming"
            else:
                continue

        if not remainder or len(remainder) < 2:
            continue

        # Bereinigung
        folder = remainder.replace("\\\\", "/").replace("\\", "/").strip("/")
        # Nested templates entfernen: {{P|uid}}, {{p|...}}
        folder = re.sub(r'\{\{[pP]\|[^}]*\}\}', '', folder).strip("/")
        folder = re.sub(r'\}\}', '', folder).strip("/")
        folder = re.sub(r'<[^>]+>', '', folder).strip("/")
        folder = folder.rstrip("/")

        if len(folder) < 2:
            continue

        return {
            "folder": folder,
            "name": game_name,
            "icon": get_icon(game_name),
            "location": location
        }

    return None


def get_icon(name):
    n = name.lower()
    for kw, icon in ICONS.items():
        if kw in n:
            return icon
    return "🎮"


def main():
    print("=" * 60)
    print("PCGamingWiki Game Save Scraper v3")
    print("=" * 60)

    db = {"version": "1.0.0", "updated": "", "games": []}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)

    existing = {g["name"].lower() for g in db["games"]}
    print(f"Existierend: {len(db['games'])} Spiele")

    all_games = list(dict.fromkeys(POPULAR_GAMES))
    print(f"Prüfe {len(all_games)} Spiele...")

    new_count = 0
    for i, title in enumerate(all_games):
        if title.lower() in existing:
            continue

        print(f"  [{i+1}/{len(all_games)}] {title}...", end=" ", flush=True)

        wikitext = get_save_wikitext(title)
        if not wikitext:
            print("❌ Kein Save-Abschnitt")
            time.sleep(0.5)
            continue

        result = parse_paths(wikitext, title)
        if result:
            db["games"].append(result)
            existing.add(title.lower())
            new_count += 1
            print(f"✅ {result['location']}: {result['folder']}")
        else:
            print(f"⚠️ Nur Steam/Cloud (kein lokaler Pfad)")

        time.sleep(1)

    db["games"].sort(key=lambda g: g["name"].lower())
    db["updated"] = str(date.today())
    v = db.get("version", "1.0.0").split(".")
    v[-1] = str(int(v[-1]) + 1)
    db["version"] = ".".join(v)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"✅ {new_count} neue Spiele hinzugefügt")
    print(f"📦 Gesamt: {len(db['games'])} Spiele")
    print(f"📋 Version: {db['version']} ({db['updated']})")


if __name__ == "__main__":
    main()
