"""
PCGamingWiki Game Save Location Scraper
Scrapt die beliebtesten Spiele von PCGamingWiki und extrahiert Save-Pfade.
Wird als GitHub Action 1x pro Woche ausgeführt.
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

API_URL = "https://www.pcgamingwiki.com/w/api.php"
OUTPUT_FILE = "gamesaves.json"

# Bekannte Windows-Pfad-Variablen → unsere Location-Typen
PATH_MAPPINGS = {
    r"%USERPROFILE%\Documents": "documents",
    r"%USERPROFILE%\Saved Games": "documents",
    r"%LOCALAPPDATA%": "appdata_local",
    r"%APPDATA%": "appdata_roaming",
    r"%USERPROFILE%\AppData\LocalLow": "appdata_locallow",
    r"%USERPROFILE%\AppData\Local": "appdata_local",
    r"%USERPROFILE%\AppData\Roaming": "appdata_roaming",
}

# Emoji-Zuordnung nach Genre/Name
GENRE_ICONS = {
    "rpg": "⚔️", "action": "🎮", "shooter": "🔫", "strategy": "🏰",
    "simulation": "🚜", "racing": "🏎️", "horror": "👻", "survival": "🌲",
    "puzzle": "🧩", "platformer": "🍄", "adventure": "🗺️", "sports": "⚽",
    "fighting": "🥊", "sandbox": "⛏️", "mmo": "🌍", "rhythm": "🎵",
}

def get_icon(name, categories=""):
    """Bestimmt ein passendes Emoji basierend auf Spielname oder Genre."""
    combined = (name + " " + categories).lower()
    for keyword, icon in GENRE_ICONS.items():
        if keyword in combined:
            return icon
    return "🎮"


def api_request(params):
    """Macht eine Anfrage an die PCGamingWiki API."""
    params["format"] = "json"
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "BackupPro-Scraper/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  API Fehler: {e}")
        return None


def get_popular_games(limit=500):
    """Holt die am meisten besuchten Spieleseiten."""
    print(f"Hole Top-{limit} Spiele von PCGamingWiki...")
    games = []
    
    # Methode 1: Kategorielisten durchgehen
    categories = [
        "Category:Games", 
    ]
    
    for cat in categories:
        cont = None
        while len(games) < limit:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmlimit": "50",
                "cmtype": "page",
                "cmsort": "timestamp",
                "cmdir": "desc",
            }
            if cont:
                params["cmcontinue"] = cont
            
            data = api_request(params)
            if not data or "query" not in data:
                break
            
            for member in data["query"].get("categorymembers", []):
                title = member.get("title", "")
                if title and ":" not in title:  # Keine Spezialseiten
                    games.append(title)
            
            if "continue" in data:
                cont = data["continue"].get("cmcontinue")
            else:
                break
            
            time.sleep(0.5)  # Rate limiting
    
    return list(dict.fromkeys(games))[:limit]  # Deduplizieren


def get_save_path(title):
    """Extrahiert den Save-Pfad eines Spiels aus dem Wikitext."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
    }
    
    data = api_request(params)
    if not data or "parse" not in data:
        return None
    
    wikitext = data["parse"].get("wikitext", {}).get("*", "")
    if not wikitext:
        return None
    
    # Suche nach Save Game Data Location Template
    # Pattern: {{Game data/saves|Windows|...path...}}
    patterns = [
        r'\{\{Game data/saves?\|Windows\|([^}]+)\}\}',
        r'\{\{Game data/config\|Windows\|([^}]+)\}\}',
        r'\{\{Game data\|[^|]*\|Windows\|([^}]+)\}\}',
        r'save[s]?\s*(?:game)?\s*(?:data)?\s*location.*?Windows.*?\|([^}|]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, wikitext, re.IGNORECASE | re.DOTALL)
        for match in matches:
            # Pfad extrahieren und normalisieren
            path = match.strip()
            # Pipe-getrennte Parameter - erster ist oft der Pfad
            parts = path.split("|")
            for part in parts:
                part = part.strip()
                if "%" in part or "\\" in part or "/" in part:
                    return parse_wiki_path(part, title)
    
    return None


def parse_wiki_path(raw_path, game_name):
    """Konvertiert einen Wiki-Pfad in unser JSON-Format."""
    path = raw_path.strip()
    
    # Bestimme Location und relativen Pfad
    location = None
    folder = None
    
    for prefix, loc_type in PATH_MAPPINGS.items():
        prefix_lower = prefix.lower().replace("\\", "/")
        path_check = path.lower().replace("\\", "/")
        
        if path_check.startswith(prefix_lower.lower()):
            location = loc_type
            folder = path[len(prefix):].strip("\\/").replace("\\", "/")
            break
    
    if not location or not folder:
        # Versuche einfacheres Matching
        if "documents" in path.lower() or "my documents" in path.lower():
            location = "documents"
            # Alles nach Documents/ extrahieren
            match = re.search(r'documents[/\\](.+)', path, re.IGNORECASE)
            if match:
                folder = match.group(1).replace("\\", "/").strip("/")
        elif "appdata" in path.lower():
            if "locallow" in path.lower():
                location = "appdata_locallow"
            elif "local" in path.lower() and "roaming" not in path.lower():
                location = "appdata_local"
            else:
                location = "appdata_roaming"
            match = re.search(r'(?:local|roaming|locallow)[/\\](.+)', path, re.IGNORECASE)
            if match:
                folder = match.group(1).replace("\\", "/").strip("/")
    
    if location and folder:
        # Bereinigung
        folder = folder.rstrip("/")
        folder = re.sub(r'\s*<[^>]+>\s*', '', folder)  # HTML-Tags entfernen
        folder = folder.strip()
        
        if len(folder) > 2 and not folder.startswith("{{"):
            return {
                "folder": folder,
                "name": game_name,
                "icon": get_icon(game_name),
                "location": location
            }
    
    return None


def load_existing():
    """Lädt die existierende gamesaves.json."""
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"version": "1.0.0", "updated": "", "games": []}


def main():
    print("=" * 60)
    print("PCGamingWiki Game Save Scraper")
    print("=" * 60)
    
    # Existierende Datenbank laden
    db = load_existing()
    existing_names = {g["name"].lower() for g in db["games"]}
    print(f"Existierende Einträge: {len(db['games'])}")
    
    # Spiele von PCGamingWiki holen
    games = get_popular_games(500)
    print(f"\n{len(games)} Spiele zum Prüfen gefunden")
    
    new_games = 0
    for i, title in enumerate(games):
        if title.lower() in existing_names:
            continue
        
        print(f"  [{i+1}/{len(games)}] {title}...", end=" ")
        result = get_save_path(title)
        
        if result:
            db["games"].append(result)
            existing_names.add(title.lower())
            new_games += 1
            print(f"✅ {result['location']}: {result['folder']}")
        else:
            print("❌ Kein Save-Pfad gefunden")
        
        time.sleep(1)  # Rate limiting (1 request/sec)
    
    # Sortieren und speichern
    db["games"].sort(key=lambda g: g["name"].lower())
    
    from datetime import date
    db["updated"] = str(date.today())
    
    # Version erhöhen
    parts = db.get("version", "1.0.0").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    db["version"] = ".".join(parts)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"Fertig! {new_games} neue Spiele hinzugefügt")
    print(f"Gesamt: {len(db['games'])} Spiele in der Datenbank")
    print(f"Version: {db['version']} ({db['updated']})")


if __name__ == "__main__":
    main()
