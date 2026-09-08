"""Tiny dependency-free inline-SVG charts for the dashboard.

Single-series only (no legend needed — the title names the series). Thin marks,
recessive axes, baseline-anchored bars, native <title> tooltips so hover works
with zero JavaScript. Committed to the dark theme.
"""

from html import escape

TEAL = "#2fd0bd"   # practice / positive metrics
AMBER = "#f2b45a"  # urge / caution metrics
GRID = "rgba(255,255,255,0.07)"
INK_MUTED = "#7c9296"


def _empty(w, h, msg="no data yet"):
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
        f'aria-label="{escape(msg)}"><text x="{w/2}" y="{h/2}" '
        f'fill="{INK_MUTED}" font-size="12" text-anchor="middle" '
        f'dominant-baseline="middle">{escape(msg)}</text></svg>'
    )


def sparkline(points, color=TEAL, w=520, h=90, pad=10, fixed_max=None):
    """points: list of (label, value|None). Draws a line with gaps + hover dots."""
    vals = [v for _, v in points if v is not None]
    if not vals:
        return _empty(w, h)
    lo = 0
    hi = fixed_max if fixed_max is not None else max(vals)
    hi = hi or 1
    n = len(points)
    span = max(n - 1, 1)

    def xy(i, v):
        x = pad + (w - 2 * pad) * i / span
        y = h - pad - (h - 2 * pad) * (v - lo) / (hi - lo)
        return x, y

    # break the polyline wherever data is missing
    segs, cur = [], []
    for i, (_, v) in enumerate(points):
        if v is None:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
        else:
            cur.append(xy(i, v))
    if len(cur) > 1:
        segs.append(cur)

    paths = "".join(
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" points="'
        + " ".join(f"{x:.1f},{y:.1f}" for x, y in seg) + '"/>'
        for seg in segs
    )
    dots = ""
    for i, (label, v) in enumerate(points):
        if v is None:
            continue
        x, y = xy(i, v)
        dots += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="transparent">'
            f'<title>{escape(str(label))}: {v}</title></circle>'
        )
    base = h - pad
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img">'
        f'<line x1="{pad}" y1="{base}" x2="{w-pad}" y2="{base}" '
        f'stroke="{GRID}" stroke-width="1"/>{paths}{dots}</svg>'
    )


def bars(items, color=AMBER, w=520, h=120, pad=14, label_key="label",
         value_key="value"):
    """items: list of dicts with label/value (+ optional 'title'). Vertical bars."""
    vals = [it[value_key] for it in items]
    if not any(vals):
        return _empty(w, h)
    hi = max(vals) or 1
    n = len(items)
    gap = 2
    slot = (w - 2 * pad) / n
    bw = max(slot - gap - 6, 4)
    base = h - pad - 14  # leave room for x labels
    body = ""
    for i, it in enumerate(items):
        v = it[value_key]
        bh = (base - pad) * v / hi
        x = pad + i * slot + (slot - bw) / 2
        y = base - bh
        title = escape(str(it.get("title", f'{it[label_key]}: {v}')))
        r = min(4, bw / 2)
        body += (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'rx="{r:.1f}" fill="{color}"><title>{title}</title></rect>'
        )
        if v:
            body += (
                f'<text x="{x + bw/2:.1f}" y="{y-4:.1f}" fill="{INK_MUTED}" '
                f'font-size="10" text-anchor="middle">{v}</text>'
            )
        body += (
            f'<text x="{x + bw/2:.1f}" y="{base+12:.1f}" fill="{INK_MUTED}" '
            f'font-size="9.5" text-anchor="middle">{escape(str(it[label_key]))}</text>'
        )
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img">'
        f'<line x1="{pad}" y1="{base}" x2="{w-pad}" y2="{base}" '
        f'stroke="{GRID}" stroke-width="1"/>{body}</svg>'
    )


def hbars(items, color=TEAL, w=520, row_h=26, pad=6):
    """items: list of (label, value). Horizontal bars, good for category counts."""
    if not items:
        return _empty(w, 60)
    hi = max(v for _, v in items) or 1
    label_w = 150
    bar_max = w - label_w - 40
    h = pad * 2 + row_h * len(items)
    body = ""
    for i, (label, v) in enumerate(items):
        y = pad + i * row_h
        bw = bar_max * v / hi
        body += (
            f'<text x="0" y="{y + row_h/2:.1f}" fill="{INK_MUTED}" font-size="11" '
            f'dominant-baseline="middle">{escape(str(label))}</text>'
            f'<rect x="{label_w}" y="{y+5:.1f}" width="{bw:.1f}" height="{row_h-12}" '
            f'rx="3" fill="{color}"><title>{escape(str(label))}: {v}</title></rect>'
            f'<text x="{label_w + bw + 6:.1f}" y="{y + row_h/2:.1f}" fill="{INK_MUTED}" '
            f'font-size="11" dominant-baseline="middle">{v}</text>'
        )
    return f'<svg viewBox="0 0 {w} {h}" width="100%" role="img">{body}</svg>'
