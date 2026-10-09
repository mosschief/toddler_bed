"""Bounding-box nesting onto square CNC-sized panels (MaxRects, best short side fit)."""
import random
from dataclasses import dataclass


@dataclass
class Placed:
    item: object
    x: float
    y: float
    w: float
    h: float
    rotated: bool


class _Bin:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.free = [(0.0, 0.0, w, h)]
        self.placed = []

    def find(self, w, h, allow_rotate):
        best = None
        for fx, fy, fw, fh in self.free:
            for rw, rh, rot in ((w, h, False), (h, w, True)) if allow_rotate else ((w, h, False),):
                if rw <= fw + 1e-9 and rh <= fh + 1e-9:
                    score = (min(fw - rw, fh - rh), max(fw - rw, fh - rh))
                    if best is None or score < best[0]:
                        best = (score, fx, fy, rw, rh, rot)
        return best

    def place(self, x, y, w, h):
        new_free = []
        for fx, fy, fw, fh in self.free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                new_free.append((fx, fy, fw, fh))
                continue
            if x > fx:
                new_free.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                new_free.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                new_free.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                new_free.append((fx, y + h, fw, fy + fh - y - h))
        # prune rects contained in others
        pruned = []
        for i, a in enumerate(new_free):
            if not any(i != j and _contains(b, a) and (b != a or j < i) for j, b in enumerate(new_free)):
                pruned.append(a)
        self.free = pruned


def _contains(a, b):
    return (b[0] >= a[0] - 1e-9 and b[1] >= a[1] - 1e-9
            and b[0] + b[2] <= a[0] + a[2] + 1e-9 and b[1] + b[3] <= a[1] + a[3] + 1e-9)


SORTS = [
    lambda s: (max(s), min(s)),
    lambda s: s[0] * s[1],
    lambda s: (s[1], s[0]),
    lambda s: (s[0], s[1]),
    lambda s: s[0] + s[1],
]


def nest(items, sizes, sheet, margin, spacing, allow_rotate=True):
    """items: list of objects; sizes: list of (w, h). Returns list of sheets (lists of Placed).

    Tries several part orderings and keeps the one using the fewest panels
    (ties go to the layout whose last panel is emptiest, i.e. most offcut).
    """
    rng = random.Random(1)
    orders = [sorted(range(len(items)), key=lambda i: key(sizes[i]), reverse=True) for key in SORTS]
    for _ in range(400):  # plus shuffled variations of the best guess
        o = list(orders[0])
        for _ in range(3):
            a, b = rng.randrange(len(o)), rng.randrange(len(o))
            o[a], o[b] = o[b], o[a]
        orders.append(o)
    best = None
    for order in orders:
        sheets = _nest_order(items, sizes, order, sheet, margin, spacing, allow_rotate)
        last_fill = sum(pl.w * pl.h for pl in sheets[-1])
        score = (len(sheets), last_fill)
        if best is None or score < best[0]:
            best = (score, sheets)
    return best[1]


def _nest_order(items, sizes, order, sheet, margin, spacing, allow_rotate):
    usable = sheet - 2 * margin + spacing
    bins = []
    for i in order:
        w, h = sizes[i]
        w, h = w + spacing, h + spacing
        for b in bins:
            f = b.find(w, h, allow_rotate)
            if f:
                break
        else:
            b = _Bin(usable, usable)
            bins.append(b)
            f = b.find(w, h, allow_rotate)
            if not f:
                raise ValueError(f"part {getattr(items[i], 'name', i)} ({sizes[i][0]:.2f} x "
                                 f"{sizes[i][1]:.2f}) does not fit the {sheet}\" CNC bed")
        _, x, y, rw, rh, rot = f
        b.place(x, y, rw, rh)
        b.placed.append(Placed(items[i], x + margin, y + margin, rw - spacing, rh - spacing, rot))
    return [b.placed for b in bins]
