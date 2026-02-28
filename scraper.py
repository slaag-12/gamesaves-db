"""
PCGamingWiki Game Save Location Scraper v2
Scrapt beliebte Spiele von PCGamingWiki und extrahiert Save-Pfade.
Wird als GitHub Action 1x pro Woche ausgeführt.

Format auf PCGamingWiki:
  {{Game data/saves|Windows|{{p|userprofile\Documents}}\My Games\Skyrim\Saves\}}
  {{Game data/saves|Windows|{{p|localappdata}}\Elden Ring\}}
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

# PCGamingWiki {{p|...}} Templates → unsere Location-Typen
P_MAPPINGS = {
    "userprofile\\documents": ("documents", ""),
    "userprofile/documents": ("documents", ""),
    "userprofile\\my documents": ("documents", ""),
    "userprofile/my documents": ("documents", ""),
    "userprofile\\saved games": ("documents", "Saved Games/"),
    "localappdata": ("appdata_local", ""),
    "appdata": ("appdata_roaming", ""),
    "locallow": ("appdata_locallow", ""),
}

GENRE_ICONS = {
    "rpg": "⚔️", "action": "🎮", "shooter": "🔫", "strategy": "🏰",
    "simulation": "🚜", "racing": "🏎️", "horror": "👻", "survival": "🌲",
    "puzzle": "🧩", "platformer": "🍄", "adventure": "🗺️", "sports": "⚽",
    "sandbox": "⛏️", "mmo": "🌍", "rhythm": "🎵",
}

# Liste populärer Spiele die garantiert Save-Pfade haben
POPULAR_GAMES = [
    "Elden Ring", "Baldur's Gate 3", "Cyberpunk 2077", "Starfield",
    "Hogwarts Legacy", "Palworld", "Lethal Company", "Helldivers 2",
    "Dragon's Dogma 2", "Lies of P", "Alan Wake 2", "Remnant II",
    "Armored Core VI: Fires of Rubicon", "Resident Evil 4 (2023)",
    "Dead Space (2023)", "Hi-Fi Rush", "Wo Long: Fallen Dynasty",
    "The Last of Us Part I", "Returnal", "God of War Ragnarök",
    "Spider-Man Remastered", "Spider-Man: Miles Morales",
    "Horizon Zero Dawn", "Horizon Forbidden West", "Death Stranding",
    "Red Dead Redemption 2", "Grand Theft Auto V",
    "The Witcher 3: Wild Hunt", "Cyberpunk 2077",
    "The Elder Scrolls V: Skyrim", "The Elder Scrolls V: Skyrim Special Edition",
    "Fallout 4", "Fallout: New Vegas", "Fallout 3", "Starfield",
    "Dark Souls III", "Dark Souls II: Scholar of the First Sin", "Dark Souls: Remastered",
    "Sekiro: Shadows Die Twice", "Elden Ring",
    "Minecraft", "Terraria", "Stardew Valley", "Valheim",
    "Subnautica", "Subnautica: Below Zero", "No Man's Sky",
    "Hades", "Hades II", "Hollow Knight", "Celeste", "Cuphead",
    "Dead Cells", "Ori and the Blind Forest", "Ori and the Will of the Wisps",
    "Disco Elysium", "Divinity: Original Sin 2",
    "Cities: Skylines", "Cities: Skylines II",
    "Sid Meier's Civilization VI", "Sid Meier's Civilization V",
    "Crusader Kings III", "Europa Universalis IV", "Hearts of Iron IV",
    "Stellaris", "Victoria 3", "Total War: Warhammer III",
    "RimWorld", "Factorio", "Satisfactory", "Oxygen Not Included",
    "Anno 1800", "Age of Empires IV", "Age of Empires II: Definitive Edition",
    "Mount & Blade II: Bannerlord", "Kingdom Come: Deliverance",
    "The Sims 4", "Planet Zoo", "Planet Coaster",
    "Euro Truck Simulator 2", "American Truck Simulator",
    "Farming Simulator 22", "Farming Simulator 25",
    "Microsoft Flight Simulator (2020)", "Forza Horizon 5", "Forza Horizon 4",
    "Resident Evil Village", "Resident Evil 2 (2019)",
    "Monster Hunter: World", "Monster Hunter Rise",
    "Assassin's Creed Valhalla", "Assassin's Creed Odyssey",
    "Far Cry 6", "Far Cry 5", "Watch Dogs: Legion",
    "Mass Effect Legendary Edition", "Dragon Age: Inquisition",
    "Borderlands 3", "Borderlands 2", "Tiny Tina's Wonderlands",
    "Doom Eternal", "Doom (2016)", "Wolfenstein II: The New Colossus",
    "Control", "Alan Wake Remastered", "Quantum Break",
    "Dying Light 2: Stay Human", "Dying Light",
    "The Forest", "Sons of the Forest",
    "Deep Rock Galactic", "Sea of Thieves", "Grounded",
    "It Takes Two", "A Way Out",
    "Persona 5 Royal", "Persona 4 Golden", "Persona 3 Reload",
    "Final Fantasy VII Remake Intergrade", "Final Fantasy XVI",
    "NieR: Automata", "NieR Replicant ver.1.22474487139...",
    "Metal Gear Solid V: The Phantom Pain",
    "Devil May Cry 5", "Bayonetta",
    "Phasmophobia", "Among Us", "Fall Guys",
    "Rocket League", "Apex Legends",
    "Path of Exile", "Diablo IV", "Diablo III",
    "World of Warcraft", "Guild Wars 2",
    "Football Manager 2024", "Football Manager 2025",
    "FIFA 24", "EA Sports FC 25",
    "Outer Wilds", "Inscryption", "Slay the Spire",
    "Darkest Dungeon", "Darkest Dungeon II",
    "Into the Breach", "FTL: Faster Than Light",
    "Warhammer 40,000: Darktide", "Warhammer: Vermintide 2",
    "Total War: Three Kingdoms", "Total War: Rome II",
    "Prison Architect", "Frostpunk", "Frostpunk 2",
    "Tropico 6", "Two Point Hospital", "Two Point Campus",
    "Pillars of Eternity", "Pillars of Eternity II: Deadfire",
    "Pathfinder: Wrath of the Righteous", "Pathfinder: Kingmaker",
    "Wasteland 3", "XCOM 2", "Phoenix Point",
    "Ghostrunner", "Ultrakill", "Vampire Survivors",
    "Dave the Diver", "Dredge", "Tunic",
    "Ready or Not", "Ground Branch", "Arma 3",
    "Kenshi", "Dwarf Fortress",
    "Manor Lords", "Against the Storm",
    "Enshrouded", "V Rising",
    "Wuthering Waves", "Genshin Impact",
    "Like a Dragon: Infinite Wealth", "Yakuza: Like a Dragon",
    "Star Wars Jedi: Survivor", "Star Wars Jedi: Fallen Order",
    "Titanfall 2", "Battlefield V", "Battlefield 2042",
    "Call of Duty: Modern Warfare II (2022)", "Call of Duty: Black Ops III",
    "Counter-Strike 2",
    "Tom Clancy's Rainbow Six Siege", "Tom Clancy's Ghost Recon Breakpoint",
    "Hitman: World of Assassination", "Hitman 2",
    "Just Cause 4", "Just Cause 3",
    "Saints Row (2022)", "Saints Row IV",
    "Sniper Elite 5", "Sniper Elite 4",
    "Prey (2017)", "Dishonored 2", "Deathloop",
    "BioShock Infinite", "BioShock Remastered",
    "System Shock (2023)",
]


def api_request(params):
    """API-Anfrage an PCGamingWiki."""
    params["format"] = "json"
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "BackupPro-GameSaveDB/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  API Fehler: {e}")
        return None


def get_save_section(title):
    """Holt den 'Save game data location' Abschnitt."""
    # Erst Sections holen
    data = api_request({
        "action": "parse", "page": title, "prop": "sections"
    })
    if not data or "parse" not in data:
        return None

    save_section = None
    for section in data["parse"].get("sections", []):
        line = section.get("line", "").lower()
        if "save" in line and ("game" in line or "data" in line or "location" in line):
            save_section = section.get("index")
            break

    if not save_section:
        return None

    # Section-Inhalt holen
    data2 = api_request({
        "action": "query", "titles": title,
        "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "rvsection": save_section
    })
    if not data2 or "query" not in data2:
        return None

    pages = data2["query"].get("pages", {})
    for page in pages.values():
        revs = page.get("revisions", [])
        if revs:
            return revs[0].get("slots", {}).get("main", {}).get("*", "")
    return None


def parse_save_path(wikitext, game_name):
    """Extrahiert Save-Pfad aus dem Wikitext."""
    if not wikitext:
        return None

    # Pattern: {{Game data/saves|Windows|{{p|userprofile\Documents}}\My Games\Skyrim\Saves\}}
    pattern = r'\{\{Game data/saves?\|Windows\|(.+?)(?:\}\})'
    matches = re.findall(pattern, wikitext, re.IGNORECASE)

    for match in matches:
        path = match.strip()

        # {{p|...}} Template auflösen
        p_match = re.search(r'\{\{p\|([^}]+)\}\}(.*)$', path, re.IGNORECASE)
        if not p_match:
            continue

        p_var = p_match.group(1).strip().lower()
        remainder = p_match.group(2).strip().strip("\\/ ")

        # Location bestimmen
        location = None
        prefix = ""
        for key, (loc, pref) in P_MAPPINGS.items():
            if p_var == key or p_var.replace("/", "\\") == key:
                location = loc
                prefix = pref
                break

        if not location:
            # Fallback-Erkennung
            if "document" in p_var:
                location = "documents"
            elif "localappdata" in p_var or "local app" in p_var:
                location = "appdata_local"
            elif "locallow" in p_var:
                location = "appdata_locallow"
            elif "appdata" in p_var:
                location = "appdata_roaming"
            else:
                continue

        if not remainder:
            continue

        # Bereinigung
        folder = prefix + remainder.replace("\\", "/").strip("/")
        # Wiki-Reste entfernen
        folder = re.sub(r'\{\{[^}]*\}\}', '', folder).strip("/")
        folder = re.sub(r'<[^>]+>', '', folder).strip("/")
        folder = folder.rstrip("/")

        if len(folder) < 2:
            continue

        icon = get_icon(game_name)

        return {
            "folder": folder,
            "name": game_name,
            "icon": icon,
            "location": location
        }

    return None


def get_icon(name):
    """Emoji basierend auf Spielname."""
    n = name.lower()
    for kw, icon in GENRE_ICONS.items():
        if kw in n:
            return icon
    return "🎮"


def get_category_games(limit=300):
    """Holt Spiele aus beliebten Kategorien."""
    games = set()
    categories = [
        "Category:Games_with_Gold_rating",
        "Category:Games_with_Silver_rating",
    ]
    for cat in categories:
        cont = None
        while len(games) < limit:
            params = {
                "action": "query", "list": "categorymembers",
                "cmtitle": cat, "cmlimit": "50", "cmtype": "page"
            }
            if cont:
                params["cmcontinue"] = cont
            data = api_request(params)
            if not data or "query" not in data:
                break
            for m in data["query"].get("categorymembers", []):
                t = m.get("title", "")
                if t and ":" not in t:
                    games.add(t)
            if "continue" in data:
                cont = data["continue"].get("cmcontinue")
            else:
                break
            time.sleep(0.5)
    return list(games)


def main():
    print("=" * 60)
    print("PCGamingWiki Game Save Scraper v2")
    print("=" * 60)

    db = {"version": "1.0.0", "updated": "", "games": []}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)

    existing = {g["name"].lower() for g in db["games"]}
    print(f"Existierend: {len(db['games'])} Spiele")

    # Beliebte Spiele + Kategorie-Spiele kombinieren
    all_games = list(dict.fromkeys(POPULAR_GAMES))
    print(f"Prüfe {len(all_games)} populäre Spiele...")

    cat_games = get_category_games(200)
    print(f"+ {len(cat_games)} Spiele aus Wiki-Kategorien")
    for g in cat_games:
        if g not in all_games:
            all_games.append(g)

    new_count = 0
    for i, title in enumerate(all_games):
        if title.lower() in existing:
            continue

        print(f"  [{i+1}/{len(all_games)}] {title}...", end=" ", flush=True)

        wikitext = get_save_section(title)
        if not wikitext:
            print("❌ Kein Save-Abschnitt")
            time.sleep(0.5)
            continue

        result = parse_save_path(wikitext, title)
        if result:
            db["games"].append(result)
            existing.add(title.lower())
            new_count += 1
            print(f"✅ {result['location']}: {result['folder']}")
        else:
            print(f"❌ Pfad nicht parsbar")

        time.sleep(1)

    # Sortieren + speichern
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
