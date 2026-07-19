# Board parametrisation. All dimensions in metres.
# Defaults approximate a typical commercial panel (955x536x66 mm, 6x22 modules).

from dataclasses import dataclass, asdict


@dataclass
class BoardParams:
    # grid
    rows: int = 6
    cols: int = 22
    pitch_x: float = 0.0403     # horizontal cell spacing
    pitch_y: float = 0.0788     # vertical cell spacing
    margin_x: float = 0.0342    # left/right margin to the first cell
    margin_y: float = 0.0316    # top/bottom margin

    # cell opening in the front plate
    hole_w: float = 0.0385
    hole_h: float = 0.0680
    recess: float = 0.0040      # depth of the opening walls down to the flap plane
    cavity: float = 0.0140      # dark cell rear wall (behind the flap)

    # flap card (one card = half a glyph, rotates about the split axis)
    flap_w: float = 0.0355
    flap_h: float = 0.0660      # total height of both halves incl. axis gap
    flap_t: float = 0.0008      # card thickness
    axis_gap: float = 0.0008    # gap at the split axis
    flap_y: float = 0.0040      # axis depth behind the front-plate plane (y=0)
    card_lift: float = 0.0002   # the card sits this far in FRONT of its rest plane
    rest_tilt_deg: float = 5.0  # rest tilt: top -5deg, bottom +175deg

    # axle pins (hints at the spool left/right of the card)
    pin_r: float = 0.0013
    pin_len: float = 0.0012
    pin_segs: int = 5

    # enclosure
    case_depth: float = 0.0660
    chamfer: float = 0.0020

    # flap-stack hint (curved strips at top/bottom of the cell)
    bulge_r: float = 0.0040
    bulge_segs: int = 4

    # ---- derived ----
    @property
    def board_w(self) -> float:
        return self.cols * self.pitch_x + 2 * self.margin_x

    @property
    def board_h(self) -> float:
        return self.rows * self.pitch_y + 2 * self.margin_y

    @property
    def card_h(self) -> float:
        """Height of one half-card (excluding the axis gap)."""
        return (self.flap_h - self.axis_gap) / 2.0

    def cell_center(self, r: int, c: int):
        """(x, z) of the cell centre; row 0 is top, column 0 is left. Board centre = origin."""
        x = -self.board_w / 2 + self.margin_x + (c + 0.5) * self.pitch_x
        z = self.board_h / 2 - self.margin_y - (r + 0.5) * self.pitch_y
        return x, z

    def to_dict(self) -> dict:
        return asdict(self)
