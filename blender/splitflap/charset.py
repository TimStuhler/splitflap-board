# Flap order (= flip sequence = atlas order) and atlas layout.
# 64 cards: blank, A-Z, 1-9 and 0, 19 punctuation marks, 8 colour chips.

_PUNCT = "!@#$()-+&=;:'\"%,./?"

FLAPS = (
    [" "]
    + [chr(ord("A") + i) for i in range(26)]
    + list("1234567890")
    + list(_PUNCT)
    + [
        "chip:red", "chip:orange", "chip:yellow", "chip:green",
        "chip:blue", "chip:violet", "chip:white", "chip:black",
    ]
)
assert len(FLAPS) == 64, len(FLAPS)

# Approximations of the colour chips found on commercial boards (sRGB hex).
CHIP_COLORS = {
    "chip:red": "#C8102E",
    "chip:orange": "#FF6A13",
    "chip:yellow": "#FFB81C",
    "chip:green": "#00A651",
    "chip:blue": "#0072CE",
    "chip:violet": "#7D3F98",
    "chip:white": "#F2F2F2",
    "chip:black": "#0D0D0D",
}

ATLAS_COLS = 8
ATLAS_ROWS = 8

_INDEX = {ch: i for i, ch in enumerate(FLAPS)}


def char_to_index(ch: str) -> int:
    """Character -> flap index; unknown -> 0 (blank)."""
    return _INDEX.get(ch.upper() if len(ch) == 1 else ch, 0)


def uv_offset(index: int):
    """UV shift from atlas cell 0 (top left) to cell `index`.
    App contract: du = (i % 8)/8, dv = -(i // 8)/8."""
    return (index % ATLAS_COLS) / ATLAS_COLS, -(index // ATLAS_COLS) / ATLAS_ROWS


def rows_to_indices(rows_text, rows: int, cols: int):
    """List of row strings -> rows x cols flap indices, each row centred.
    'chip:' names are not addressable in running text - set those indices directly."""
    grid = [[0] * cols for _ in range(rows)]
    for r in range(min(rows, len(rows_text))):
        text = (rows_text[r] or "")[:cols]
        start = (cols - len(text)) // 2
        for k, ch in enumerate(text):
            grid[r][start + k] = char_to_index(ch)
    return grid


def hex_to_linear(hex_str: str, alpha: float = 1.0):
    """sRGB hex -> linear RGBA tuple (Blender expects linear)."""
    h = hex_str.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (*[lin(c) for c in rgb], alpha)
