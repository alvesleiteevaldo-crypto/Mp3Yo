from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path("app_icon.ico")
SIZE = 256

img = Image.new("RGBA", (SIZE, SIZE), (5, 16, 30, 255))
px = img.load()

# Blue -> green diagonal background gradient.
for y in range(SIZE):
    for x in range(SIZE):
        t = (x + y) / (2 * (SIZE - 1))
        r = int(7 + 8 * t)
        g = int(45 + 150 * t)
        b = int(120 + 30 * (1 - t))
        px[x, y] = (r, g, b, 255)

draw = ImageDraw.Draw(img)

# Rounded dark inner tile.
margin = 18
draw.rounded_rectangle(
    (margin, margin, SIZE - margin, SIZE - margin),
    radius=48,
    fill=(4, 20, 35, 238),
    outline=(44, 220, 180, 255),
    width=6,
)

# Circular conversion arrow.
bbox = (52, 50, 205, 203)
draw.arc(bbox, start=35, end=320, fill=(47, 212, 255, 255), width=18)
draw.polygon([(185, 51), (218, 77), (181, 91)], fill=(71, 255, 154, 255))

# Play triangle.
draw.polygon([(101, 91), (101, 166), (164, 128)], fill=(70, 255, 170, 255))

# Download arrow.
draw.rectangle((169, 151, 188, 205), fill=(71, 255, 154, 255))
draw.polygon([(151, 191), (206, 191), (179, 221)], fill=(71, 255, 154, 255))

img.save(OUT, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(OUT)
