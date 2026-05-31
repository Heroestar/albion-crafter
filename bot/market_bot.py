"""
Albion Market Bot
Navigeert automatisch door marktcategorieën en leest prijzen via screenshot-OCR.
Geen packet scanner nodig.

Gebruik:
  1. Open Albion Online, ga naar de markt in Brecilien
  2. Run dit script: python market_bot.py
  3. Kalibreer bij eerste start de UI-elementen
  4. Zet muis in een schermhoek om direct te stoppen (failsafe)

Vereisten: pip install pyautogui pillow pytesseract requests
           + Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
"""

import pyautogui
import time
import json
import os
import re
import threading
import queue
from datetime import datetime, timezone

import requests
from PIL import Image, ImageEnhance, ImageFilter

# ── Instellingen ───────────────────────────────────────────────────────────
SCAN_WAIT  = 2.5
ITEM_H     = 23
SUBMENU_DX = 160

SUPABASE_URL = "https://huhpjepvqfkuezxmxnuw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1aHBqZXB2cWZrdWV6eG14bnV3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxMTE5MzUsImV4cCI6MjA5NDY4NzkzNX0.ql9Zzbrj4ohh_jsrt1KHxP5XK8_SEMyMW3XGNx4WtvQ"

KNOWN_CITIES = [
    "Bridgewatch", "Fort Sterling", "Lymhurst", "Martlock",
    "Thetford", "Caerleon", "Brecilien", "Black Market",
]

def normalize_city(raw):
    raw_lower = raw.lower().replace(" ", "")
    for city in KNOWN_CITIES:
        if city.lower().replace(" ", "") == raw_lower:
            return city
    return raw.title()
CITY_NAME_W  = 220   # breedte screenshot stadsnaam
CITY_NAME_H  = 30    # hoogte screenshot stadsnaam

pyautogui.PAUSE    = 0.25
pyautogui.FAILSAFE = True

RESOURCES = ["metal_bars", "leather", "planks"]
SWORDS    = ["broadsword", "claymore", "dual_swords", "clarent_blade",
             "carving_sword", "galatine_pair", "kingmaker", "infinity_blade"]
TIERS     = [4, 5, 6, 7, 8]
ENCHANTS  = [0, 1, 2, 3, 4]

CALIBRATION_FILE = "bot_calibration.json"

# ── Item ID mapping ────────────────────────────────────────────────────────
_RESOURCE_BASE = {
    "metal_bars": "METALBAR",
    "leather":    "LEATHER",
    "planks":     "PLANKS",
}
_SWORD_BASE = {
    "broadsword":    "MAIN_SWORD",
    "claymore":      "2H_CLAYMORE",
    "dual_swords":   "2H_DUALSWORD",
    "clarent_blade": "MAIN_SCIMITAR_MORGANA",
    "carving_sword": "2H_CLEAVER_HELL",
    "galatine_pair": "2H_DUALSCIMITAR_UNDEAD",
    "kingmaker":     "2H_CLAYMORE_AVALON",
    "infinity_blade":"MAIN_SWORD_CRYSTAL",
}

def make_item_id(name, tier, enchant):
    base_key = _RESOURCE_BASE.get(name) or _SWORD_BASE.get(name)
    if not base_key:
        return None
    base = f"T{tier}_{base_key}"
    if enchant == 0:
        return base
    if name in _RESOURCE_BASE:
        return f"{base}_LEVEL{enchant}@{enchant}"
    return f"{base}@{enchant}"

# ── Supabase upload queue ──────────────────────────────────────────────────
_upload_q = queue.Queue()

def _uploader():
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates",
    }
    while True:
        row = _upload_q.get()
        if row is None:
            break
        row["created_at"] = datetime.now(timezone.utc).isoformat()
        try:
            r = requests.post(f"{SUPABASE_URL}/rest/v1/price_history",
                              headers=headers, json=[row], timeout=10)
            if r.status_code not in (200, 201):
                print(f"  [upload fout] {r.status_code}")
        except Exception as e:
            print(f"  [upload fout] {e}")
        _upload_q.task_done()

# ── Prijs lezen via screenshot + OCR ──────────────────────────────────────
try:
    import pytesseract
    # Tesseract staat in de tesseract/ submap naast dit script
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _TESS_PATH  = os.path.join(_SCRIPT_DIR, "tesseract", "tesseract.exe")
    if os.path.exists(_TESS_PATH):
        pytesseract.pytesseract.tesseract_cmd = _TESS_PATH
    _OCR_OK = True
except ImportError:
    _OCR_OK = False
    print("  [!] pytesseract niet gevonden — pip install pytesseract")

PRICE_REGION_W = 400  # breed gebied om te zoeken
PRICE_REGION_H = 26   # hoogte van één rij
PRICE_CROP_W   = 110  # alleen de rechterkant croppen (waar prijs altijd staat)

def read_lowest_price(cal):
    """Screenshot het gekalibreerde rechthoekje en lees de prijs."""
    if not _OCR_OK or "price_x" not in cal:
        return None
    try:
        x1 = int(cal["price_x"])
        y1 = int(cal["price_y"])
        x2 = int(cal.get("price_x2", x1 + 120))
        y2 = int(cal.get("price_y2", y1 + 22))
        w  = max(x2 - x1, 20)
        h  = max(y2 - y1, 10)
        img = pyautogui.screenshot(region=(x1, y1, w, h))


        # Schaal 3x, grayscale, threshold voor scherpe zwart/wit tekst
        w, h = img.size
        img2 = img.resize((w * 3, h * 3), Image.LANCZOS)
        img2 = img2.convert("L")
        # Harde drempelwaarde: tekst donker (<160) → zwart, achtergrond → wit
        img2 = img2.point(lambda p: 0 if p < 160 else 255)
        img2.save("debug_price_processed.png")

        raw = pytesseract.image_to_string(img2, config="--psm 6 --oem 1").strip()
        print(f"  [OCR] '{raw[:60]}'")  # toon wat OCR leest

        candidates = []
        for token in re.findall(r'[\d,\.]+', raw):
            digits = re.sub(r'[^0-9]', '', token)
            if len(digits) >= 2:
                val = int(digits)
                if 100 <= val <= 100_000_000:
                    candidates.append(val)

        return min(candidates) if candidates else None
    except Exception:
        return None

def detect_city(cal):
    """Lees de stadsnaam uit de markttitel via OCR."""
    if not _OCR_OK or "city_x" not in cal:
        return None
    try:
        x = int(cal["city_x"])
        y = int(cal["city_y"])
        img = pyautogui.screenshot(region=(x, y, CITY_NAME_W, CITY_NAME_H))
        img = img.resize((CITY_NAME_W * 2, CITY_NAME_H * 2), Image.LANCZOS)
        img = img.convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.5)
        raw = pytesseract.image_to_string(img, config="--psm 7").strip()
        # Match aan bekende stad
        raw_lower = raw.lower()
        for city in KNOWN_CITIES:
            if city.lower() in raw_lower:
                return city
        return raw if raw else None
    except Exception:
        return None

# ── Kalibratie ────────────────────────────────────────────────────────────
def _save(cal):
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(cal, f, indent=2)

def calibrate():
    print("\n=== KALIBRATIE ===")
    print("Beweeg je muis naar het element en druk Enter.\n")

    # Laad eventueel al opgeslagen tussenstand
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE) as f:
            cal = json.load(f)
    else:
        cal = {}

    def record(label):
        input(f"  → Hover over {label}, druk Enter...")
        pos = pyautogui.position()
        print(f"    Opgeslagen: x={pos.x}, y={pos.y}")
        return {"x": pos.x, "y": pos.y}

    def step(key, label, extra_print=None):
        if key in cal:
            print(f"  ✓ {key} al bekend ({cal[key]}), overgeslagen.")
            return
        if extra_print:
            print(extra_print)
        cal[key] = record(label)
        _save(cal)

    # ── Categorie dropdown ────────────────────────────────────────
    step("category", "CATEGORIE DROPDOWN (bijv. 'Leather' of 'All')")

    step("cat_item0", "EERSTE menu-item in categorie-dropdown",
         "\n  Open nu het categorie-dropdown in Albion (klik erop).\n"
         "  Hover dan over het EERSTE item in de lijst ('All' of 'Weapons').")

    step("cat_crafting", "'Crafting' in het categorie-dropdown",
         "\n  Hover nu over 'Crafting' in datzelfde open dropdown.")

    if "item_h" not in cal and "cat_crafting" in cal and "cat_item0" in cal:
        crafting_idx = CATEGORY_ITEMS.index("Crafting")
        item_h = (cal["cat_crafting"]["y"] - cal["cat_item0"]["y"]) / crafting_idx
        cal["item_h"] = round(item_h, 1)
        print(f"    Item-hoogte berekend: {cal['item_h']:.1f} px")
        _save(cal)

    # ── Submenu posities ──────────────────────────────────────────
    if "submenu_dx" not in cal:
        print("\n  Hover nu over 'Crafting' opnieuw (submenu mag al open zijn).")
        crafting_pos = record("'Crafting' (voor submenu-offset)")
        print("  Hover nu over 'Refined Resources' in het Crafting submenu.")
        refined_pos  = record("'Refined Resources' in Crafting submenu")
        cal["submenu_dx"]  = refined_pos["x"] - crafting_pos["x"]
        cal["crafting_x"]  = crafting_pos["x"]
        cal["crafting_y"]  = crafting_pos["y"]
        cal["refined_x"]   = refined_pos["x"]
        cal["refined_y"]   = refined_pos["y"]
        print(f"    Submenu breedte: {cal['submenu_dx']} px")
        _save(cal)

    # ── Metal Bars ankerpunt ──────────────────────────────────────
    if "menu_metal_bars" not in cal:
        cx         = cal["category"]["x"]
        cy         = cal["category"]["y"]
        item_h     = cal["item_h"]
        submenu_dx = cal["submenu_dx"]

        print("\n  De bot opent nu het menu — wacht tot het submenu zichtbaar is.")
        print("  Schakel naar Albion over 4 seconden...")
        for i in range(4, 0, -1):
            print(f"    {i}...", end="\r")
            time.sleep(1)
        print()

        # Bot navigeert naar Refined Resources (zelfde pad als tijdens scannen)
        click(cx, cy)
        time.sleep(0.5)
        cat_item0_y  = cal["cat_item0"]["y"]
        crafting_idx = CATEGORY_ITEMS.index("Crafting")
        crafting_y   = cat_item0_y + crafting_idx * item_h
        hover(cx, crafting_y)

        refined_idx = CRAFTING_SUBMENU.index("Refined Resources")
        refined_x   = cx + submenu_dx
        refined_y   = crafting_y + refined_idx * item_h
        hover(refined_x, refined_y)
        time.sleep(0.5)

        # Nu wijst de gebruiker Metal Bars aan in het bot-geopende menu
        print("  Het Refined Resources submenu staat nu open.")
        print("  Hover over METAL BARS (Cloth / Leather / METAL BARS) en druk Enter.")
        while True:
            pos = record("'Metal Bars'")
            print("  Muis gaat terug naar die positie...")
            time.sleep(0.3)
            pyautogui.moveTo(int(pos["x"]), int(pos["y"]))
            time.sleep(0.8)
            antwoord = input("  Staat de muis op Metal Bars? (j/n): ").strip().lower()
            if antwoord == "j":
                break
            print("  Probeer opnieuw.")
            # Heropen menu
            click(cx, cy)
            time.sleep(0.5)
            hover(cx, crafting_y)
            hover(refined_x, refined_y)
            time.sleep(0.5)

        cal["menu_metal_bars"] = pos
        cal["menu_res_x"]      = refined_x + submenu_dx
        _save(cal)

    # ── Tier dropdown ─────────────────────────────────────────────
    step("tier", "TIER DROPDOWN (bijv. 'Tier 4')",
         "\n  Sluit eventuele menu's (Escape). Hover over de TIER DROPDOWN.")

    step("tier_item0", "EERSTE item in tier-dropdown",
         "  Open de Tier dropdown. Hover over het EERSTE item ('All Tiers' of 'Tier 2').")

    step("tier_4", "'Tier 4' in tier-dropdown",
         "  Hover over 'Tier 4' in de open dropdown.")

    step("tier_8", "'Tier 8' in tier-dropdown",
         "  Hover over 'Tier 8' in de open dropdown.")

    if "tier_item_h" not in cal and "tier_4" in cal and "tier_8" in cal:
        tier_item_h = (cal["tier_8"]["y"] - cal["tier_4"]["y"]) / 4
        cal["tier_item_h"] = round(tier_item_h, 2)
        print(f"    Tier item-hoogte: {cal['tier_item_h']:.2f} px")
        _save(cal)

    # ── Enchantment dropdown ──────────────────────────────────────
    step("enchant", "ENCHANTMENT DROPDOWN",
         "\n  Sluit menu's. Hover over de ENCHANTMENT DROPDOWN.")

    step("enchant_item0", "EERSTE item in enchantment-dropdown ('No Enchantment')",
         "  Open het enchantment dropdown. Hover over het EERSTE item ('No Enchantment').")

    # ── Swords navigatie ──────────────────────────────────────────
    if "sword_bs_y" not in cal or "sword_inf_y" not in cal:
        cx     = cal["category"]["x"]
        cy     = cal["category"]["y"]
        item_h = cal["item_h"]

        print("\n  Bot opent nu het Weapons menu voor swords-kalibratie...")
        print("  Schakel naar Albion over 4 seconden...")
        for i in range(4, 0, -1):
            print(f"    {i}...", end="\r")
            time.sleep(1)
        print()
        print("  LET OP: zet muis NIET in een hoek — dan stopt PyAutoGUI.")

        weapons_y = cal["cat_item0"]["y"] + CATEGORY_ITEMS.index("Weapons") * item_h

        try:
            # Bot navigeert naar Weapons
            click(cx, cy)
            time.sleep(0.5)
            hover(cx, weapons_y)
            time.sleep(0.5)
        except pyautogui.FailSafeException:
            print("  [!] Failsafe — muis was in een hoek. Start de bot opnieuw.")
            _save(cal)
            return cal

        print("  Weapons submenu open — hover over 'Sword' en druk Enter.")
        sword_pos = record("'Sword' in Weapons submenu")
        cal["weapons_x"] = cx
        cal["weapons_y"] = weapons_y
        cal["sword_x"]   = sword_pos["x"]
        cal["sword_y"]   = sword_pos["y"]
        _save(cal)

        try:
            # Bot navigeert naar Sword submenu
            click(cx, cy)
            time.sleep(0.5)
            hover(cx, weapons_y)
            hover(sword_pos["x"], sword_pos["y"])
            time.sleep(0.5)
        except pyautogui.FailSafeException:
            print("  [!] Failsafe — start de bot opnieuw voor de sword-items.")
            _save(cal)
            return cal

        print("  Sword submenu open.")
        print("  Hover over 'All' (eerste item) en druk Enter.")
        all_pos = record("'All' in Sword submenu")
        cal["sword_all_x"] = all_pos["x"]
        cal["sword_all_y"] = all_pos["y"]

        print("  Hover over 'Broadsword' (tweede item) en druk Enter.")
        bs_pos = record("'Broadsword'")
        cal["sword_bs_y"] = bs_pos["y"]

        print("  Hover over 'Infinity Blade' (laatste item) en druk Enter.")
        inf_pos = record("'Infinity Blade'")
        cal["sword_inf_y"] = inf_pos["y"]
        _save(cal)

    # ── Prijskolom ────────────────────────────────────────────────
    if "price_x" not in cal:
        print("\n  Navigeer naar een marktcategorie met listings.")
        print("  Hover net LINKS van het eerste cijfer van de prijs (na het muntje).")
        print("  Dit punt is altijd hetzelfde — de bot pakt 200px naar rechts.")
        pos = record("LINKS van de prijs (na het muntje)")
        cal["price_x"]  = pos["x"] - 2
        cal["price_y"]  = pos["y"] - 4
        cal["price_x2"] = pos["x"] + 200
        cal["price_y2"] = pos["y"] + 20
        _save(cal)

    _save(cal)
    print("\n  Kalibratie opgeslagen!\n")
    return cal

REQUIRED_FIELDS = [
    "category", "cat_item0", "cat_crafting", "item_h",
    "submenu_dx", "crafting_x", "crafting_y", "refined_x", "refined_y",
    "menu_metal_bars", "menu_res_x",
    "tier", "tier_item0", "tier_4", "tier_8", "tier_item_h",
    "enchant", "enchant_item0",
    "weapons_x", "weapons_y", "sword_x", "sword_y",
    "sword_all_x", "sword_all_y", "sword_bs_y", "sword_inf_y",
    "price_x", "price_y", "price_x2", "price_y2",  # rechthoek
]

def patch_calibration(cal):
    """Vraag alleen de ontbrekende velden op en sla alles opnieuw op."""
    def record(label):
        input(f"  → Hover over {label}, druk Enter...")
        pos = pyautogui.position()
        print(f"    Opgeslagen: x={pos.x}, y={pos.y}")
        return {"x": pos.x, "y": pos.y}

    changed = False

    if "menu_metal_bars" not in cal or "menu_res_x" not in cal:
        print("\n  [nieuw] Open cat → Crafting → Refined Resources → hover over 'Metal Bars'.")
        cal["menu_metal_bars"] = record("'Metal Bars' in Refined Resources submenu")
        # menu_res_x = crafting_x + 2 * submenu_dx
        cal["menu_res_x"] = cal["category"]["x"] + 2 * cal["submenu_dx"]
        changed = True

    if "tier_8" not in cal or "tier_item_h" not in cal:
        print("\n  [nieuw] Open Tier dropdown → hover over 'Tier 8'.")
        cal["tier_8"] = record("'Tier 8' in tier-dropdown")
        tier_item_h = (cal["tier_8"]["y"] - cal["tier_4"]["y"]) / 4
        cal["tier_item_h"] = round(tier_item_h, 2)
        print(f"    Tier item-hoogte: {cal['tier_item_h']:.2f} px")
        changed = True

    if changed:
        with open(CALIBRATION_FILE, "w") as f:
            json.dump(cal, f)
        print("  Kalibratie bijgewerkt.\n")
    return cal

def load_calibration(silent=False):
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE) as f:
            cal = json.load(f)
        missing = [k for k in REQUIRED_FIELDS if k not in cal]
        if not missing:
            if silent:
                return cal
            ans = input("Kalibratie gevonden — opnieuw kalibreren? (j/n): ").strip().lower()
            if ans != "j":
                return cal
        else:
            print(f"Kalibratie mist: {missing}")
            print("Alleen de nieuwe punten worden gevraagd.\n")
            return calibrate()
    return calibrate()

# ── Klikken ───────────────────────────────────────────────────────────────
def click(x, y):
    pyautogui.click(int(x), int(y))
    time.sleep(0.25)

def hover(x, y):
    pyautogui.moveTo(int(x), int(y))
    time.sleep(0.35)

# ── Markt-layout ──────────────────────────────────────────────────────────
# Albion's dropdown menu: items staan verticaal op vaste hoogte
# Categorie-menu volgorde (0-gebaseerd index):
CATEGORY_ITEMS = [
    "All", "Weapons", "Chest Armor", "Head Armor", "Foot Armor",
    "Off-Hands", "Capes", "Bags", "Mount", "Consumable",
    "Gathering Equipment", "Crafting", "Artifact", "Farming",
    "Furniture", "Vanity", "Other"
]
# Crafting-submenu:
CRAFTING_SUBMENU = ["Resources", "Refined Resources", "Artifact", "Tokens", "City Resources", "Fish", "Alchemy"]
# Refined Resources submenu:
REFINED_SUBMENU  = ["Cloth", "Leather", "Metal Bars", "Stone Block", "Planks"]
# Weapons-submenu:
WEAPONS_SUBMENU  = ["All", "Bow", "Crossbow", "Axe", "Dagger", "Hammer",
                    "War Gloves", "Mace", "Quarterstaff", "Spear", "Sword",
                    "Arcane Staff", "Cursed Staff", "Fire Staff", "Frost Staff",
                    "Holy Staff", "Nature Staff", "Shapeshifter Staff"]
# Sword-submenu (index 0=All, 1=Broadsword, ..., 8=Infinity Blade):
SWORD_SUBMENU    = ["all", "broadsword", "claymore", "dual_swords", "clarent_blade",
                    "carving_sword", "galatine_pair", "kingmaker", "infinity_blade"]

def open_resource(cal, resource):
    cx     = cal["category"]["x"]
    item_h = cal.get("item_h", ITEM_H)

    # Open categorie dropdown
    click(cx, cal["category"]["y"])
    time.sleep(0.4)

    # Hover: Crafting — gebruik gecalibreerde positie direct
    hover(cal["crafting_x"], cal["crafting_y"])

    # Hover: Refined Resources — gebruik gecalibreerde positie direct
    hover(cal["refined_x"], cal["refined_y"])

    # Klik de resource — gebruik gecalibreerd Metal Bars als ankerpunt
    mb_y  = cal["menu_metal_bars"]["y"]
    res_x = cal["menu_res_x"]
    # Cloth=0, Leather=1, Metal Bars=2, Stone Block=3, Planks=4
    # offset t.o.v. Metal Bars (index 2):
    res_offset = {"metal_bars": 0, "leather": -1, "planks": 2}
    res_y = mb_y + res_offset[resource] * item_h
    click(res_x, res_y)
    time.sleep(0.8)

def open_sword(cal, sword):
    click(cal["category"]["x"], cal["category"]["y"])
    time.sleep(0.4)

    hover(cal["weapons_x"], cal["weapons_y"])
    hover(cal["sword_x"], cal["sword_y"])

    # Bereken Y vanuit gecalibreerd Broadsword-ankerpunt
    # Infinity Blade = index 8, Broadsword = index 1 → 7 stappen
    sword_item_h = (cal["sword_inf_y"] - cal["sword_bs_y"]) / 7
    sword_idx    = SWORD_SUBMENU.index(sword)
    target_y     = cal["sword_bs_y"] + (sword_idx - 1) * sword_item_h
    click(cal["sword_all_x"], target_y)
    time.sleep(0.8)

def select_tier(cal, tier):
    """Klik tier dropdown en selecteer de juiste tier."""
    tx = cal["tier"]["x"]
    click(tx, cal["tier"]["y"])
    time.sleep(0.4)

    # Gebruik gecalibreerde T4 als ankerpunt + nauwkeurige item-hoogte (T4→T8 span)
    t4_y        = cal["tier_4"]["y"]
    tier_item_h = cal["tier_item_h"]
    offset      = {4: 0, 5: 1, 6: 2, 7: 3, 8: 4}[tier]
    click(tx, t4_y + offset * tier_item_h)
    time.sleep(0.5)

def select_enchant(cal, enchant):
    """Klik enchantment dropdown en selecteer niveau."""
    ex = cal["enchant"]["x"]
    click(ex, cal["enchant"]["y"])
    time.sleep(0.4)

    # Gebruik gecalibreerde eerste item-positie als basis
    e0_y   = cal["enchant_item0"]["y"]
    item_h = cal.get("item_h", ITEM_H)
    # Index 0 = No Enchantment, 1 = Enchantment 1, etc.
    click(ex, e0_y + enchant * item_h)
    time.sleep(0.5)

# ── Hoofd scan-loop ────────────────────────────────────────────────────────
def _scan_tier_enchant(cal, name, open_fn, count, total, errors, start):
    try:
        open_fn()
        time.sleep(1.5)  # extra wacht na categorie-wissel
    except Exception as e:
        print(f"  [!] Fout bij openen {name}: {e}")
        return count, errors + len(TIERS) * len(ENCHANTS)

    for tier in TIERS:
        try:
            select_tier(cal, tier)
        except Exception as e:
            print(f"  [!] Fout tier {tier}: {e}")
            errors += len(ENCHANTS)
            continue

        for enchant in ENCHANTS:
            try:
                select_enchant(cal, enchant)
            except Exception as e:
                print(f"  [!] Fout enchant {enchant}: {e}")
                errors += 1
                continue

            time.sleep(SCAN_WAIT)

            # Prijs lezen en uploaden
            price = read_lowest_price(cal)
            item_id = make_item_id(name, tier, enchant)
            if price and item_id:
                _upload_q.put({
                    "item_id": item_id,
                    "city":    cal.get("_current_city", "Onbekend"),
                    "tier":    f"T{tier}",
                    "price":   price,
                })
                print(f"  T{tier}.{enchant}  {price:,} silver  → {item_id}")
            else:
                print(f"  T{tier}.{enchant}  [geen prijs]")

            count += 1
            elapsed   = time.time() - start
            per_item  = elapsed / count if count else SCAN_WAIT
            remaining = int((total - count) * per_item)
            m, s = divmod(remaining, 60)
            print(f"             [{count}/{total}]  ~{m}m{s:02d}s over")

    return count, errors

def scan_all(cal):
    # Start upload thread
    uploader = threading.Thread(target=_uploader, daemon=True)
    uploader.start()

    # Stad — gebruik bestaande waarde als die al gezet is (bijv. via GUI)
    if cal.get("_current_city"):
        city = normalize_city(cal["_current_city"])
    else:
        print("  Steden: Brecilien / Fort Sterling / Bridgewatch / Lymhurst / Martlock / Thetford / Caerleon")
        city = input("  In welke stad ben je? ").strip()
        if not city:
            city = "Onbekend"
        city = normalize_city(city)
    cal["_current_city"] = city
    print(f"  Stad: {city}")

    has_swords = "sword_all_x" in cal
    total  = (len(RESOURCES) + (len(SWORDS) if has_swords else 0)) * len(TIERS) * len(ENCHANTS)
    count  = 0
    errors = 0
    start  = time.time()

    for resource in RESOURCES:
        print(f"\n── {resource.upper()} ──")
        count, errors = _scan_tier_enchant(
            cal, resource,
            lambda r=resource: open_resource(cal, r),
            count, total, errors, start
        )

    if has_swords:
        for sword in SWORDS:
            print(f"\n── {sword.upper()} ──")
            count, errors = _scan_tier_enchant(
                cal, sword,
                lambda s=sword: open_sword(cal, s),
                count, total, errors, start
            )

    _upload_q.join()  # wacht tot alle uploads klaar zijn
    _upload_q.put(None)

    elapsed = int(time.time() - start)
    m, s = divmod(elapsed, 60)
    print(f"\n{'='*50}")
    print(f"  Klaar in {m}m{s:02d}s  |  Gescand: {count}/{total}  |  Fouten: {errors}")
    print(f"{'='*50}")


def scan_all_with_cal(cal):
    """Wordt aangeroepen vanuit de GUI — slaat kalibratiestap over."""
    scan_all(cal)

if __name__ == "__main__":
    print("=" * 50)
    print("  Albion Market Bot")
    print("=" * 50)
    print("  Zet muis in een schermhoek om te stoppen.\n")

    cal = load_calibration()

    print(f"Kalibratie:")
    print(f"  Categorie : ({cal['category']['x']}, {cal['category']['y']})")
    print(f"  Tier      : ({cal['tier']['x']}, {cal['tier']['y']})")
    print(f"  Enchant   : ({cal['enchant']['x']}, {cal['enchant']['y']})")
    print()
    print("Schakel naar Albion met markt open — bot start over 6 seconden...")

    for i in range(6, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print()

    scan_all(cal)
