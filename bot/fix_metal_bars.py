"""
Bot opent het menu en jij wijst Metal Bars aan.
Zo klopt de positie exact met hoe de bot het menu opent.
"""
import json, os, pyautogui, time

CAL_FILE = "bot_calibration.json"

if not os.path.exists(CAL_FILE):
    print("Geen kalibratie gevonden — start eerst market_bot.py.")
    input("Enter om te sluiten...")
    exit()

with open(CAL_FILE) as f:
    cal = json.load(f)

CATEGORY_ITEMS   = ["All","Weapons","Chest Armor","Head Armor","Foot Armor",
                    "Off-Hands","Capes","Bags","Mount","Consumable",
                    "Gathering Equipment","Crafting","Artifact","Farming",
                    "Furniture","Vanity","Other"]
CRAFTING_SUBMENU = ["Resources","Refined Resources","Artifact","Tokens",
                    "City Resources","Fish","Alchemy"]

cx         = cal["category"]["x"]
cy         = cal["category"]["y"]
item_h     = cal["item_h"]
submenu_dx = cal["submenu_dx"]
cat_item0_y  = cal["cat_item0"]["y"]
crafting_idx = CATEGORY_ITEMS.index("Crafting")
crafting_y   = cat_item0_y + crafting_idx * item_h
refined_idx  = CRAFTING_SUBMENU.index("Refined Resources")
refined_x    = cx + submenu_dx
refined_y    = crafting_y + refined_idx * item_h

pyautogui.PAUSE    = 0.25
pyautogui.FAILSAFE = True

print("Schakel naar Albion over 4 seconden...")
for i in range(4, 0, -1):
    print(f"  {i}...", end="\r")
    time.sleep(1)
print()

def open_to_refined():
    pyautogui.click(int(cx), int(cy))
    time.sleep(0.5)
    pyautogui.moveTo(int(cx), int(crafting_y))
    time.sleep(0.4)
    pyautogui.moveTo(int(refined_x), int(refined_y))
    time.sleep(0.5)

open_to_refined()
print("Refined Resources submenu staat open.")
print("Hover over METAL BARS (Cloth / Leather / METAL BARS) en druk Enter.")

while True:
    input("  Muis op Metal Bars, druk Enter...")
    pos = pyautogui.position()
    print(f"  Opgeslagen: x={pos.x}, y={pos.y}")
    print("  Muis gaat terug naar die positie...")
    time.sleep(0.3)
    pyautogui.moveTo(int(pos.x), int(pos.y))
    time.sleep(0.8)
    antwoord = input("  Staat de muis op Metal Bars? (j/n): ").strip().lower()
    if antwoord == "j":
        break
    print("  Opnieuw — bot opent menu weer.")
    open_to_refined()

cal["menu_metal_bars"] = {"x": pos.x, "y": pos.y}
cal["menu_res_x"]      = refined_x + submenu_dx

with open(CAL_FILE, "w") as f:
    json.dump(cal, f, indent=2)

print()
print("Klaar! Start nu market_bot.py.")
input("Enter om te sluiten...")
