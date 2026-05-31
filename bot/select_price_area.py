"""
Prijsgebied selecteren — sleep een rechthoekje over de eerste prijs.
Albion moet zichtbaar zijn op de achtergrond.
"""
import tkinter as tk
import pyautogui
import json
import time
from PIL import ImageTk

CAL_FILE = "bot_calibration.json"

print("Schakel naar Albion met de markt open — selectie start over 3 seconden...")
for i in range(3, 0, -1):
    print(f"  {i}...", end="\r")
    time.sleep(1)
print()

# Screenshot als achtergrond
screenshot = pyautogui.screenshot()
sw, sh = screenshot.size

root = tk.Tk()
root.attributes("-topmost", True)
root.overrideredirect(True)
root.geometry(f"{sw}x{sh}+0+0")

canvas = tk.Canvas(root, cursor="cross", highlightthickness=0)
canvas.pack(fill="both", expand=True)

bg = ImageTk.PhotoImage(screenshot)
canvas.create_image(0, 0, anchor="nw", image=bg)
# Lichte overlay zodat het duidelijk is dat je aan het selecteren bent
canvas.create_rectangle(0, 0, sw, sh, fill="black", stipple="gray25", outline="")

label = canvas.create_text(sw//2, 30, text="Sleep over de EERSTE PRIJS  |  ESC = annuleren",
                            fill="white", font=("Arial", 16, "bold"))

start_x = start_y = 0
rect_id = None
coords = {}

def on_press(e):
    global start_x, start_y, rect_id
    start_x, start_y = e.x, e.y
    if rect_id:
        canvas.delete(rect_id)

def on_drag(e):
    global rect_id
    if rect_id:
        canvas.delete(rect_id)
    rect_id = canvas.create_rectangle(start_x, start_y, e.x, e.y,
                                       outline="red", width=3, fill="")

def on_release(e):
    coords["x1"] = min(start_x, e.x)
    coords["y1"] = min(start_y, e.y)
    coords["x2"] = max(start_x, e.x)
    coords["y2"] = max(start_y, e.y)
    root.destroy()

def on_escape(e):
    root.destroy()

canvas.bind("<ButtonPress-1>", on_press)
canvas.bind("<B1-Motion>", on_drag)
canvas.bind("<ButtonRelease-1>", on_release)
root.bind("<Escape>", on_escape)
root.mainloop()

if not coords:
    print("Geannuleerd.")
    input("Enter om te sluiten...")
    exit()

print(f"Geselecteerd: ({coords['x1']},{coords['y1']}) → ({coords['x2']},{coords['y2']})")
print(f"Breedte: {coords['x2']-coords['x1']}px  Hoogte: {coords['y2']-coords['y1']}px")

with open(CAL_FILE) as f:
    cal = json.load(f)

cal["price_x"]  = coords["x1"]
cal["price_y"]  = coords["y1"]
cal["price_x2"] = coords["x2"]
cal["price_y2"] = coords["y2"]

with open(CAL_FILE, "w") as f:
    json.dump(cal, f, indent=2)

print("Opgeslagen! Start nu de bot.")
input("Enter om te sluiten...")
