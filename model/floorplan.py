#!/usr/bin/env python3
"""
Phase 6b -- standard-cell FLOORPLAN (not a routed layout).

We have no P&R tool (OpenROAD/Innovus absent), so there is no routed GDS.  What
IS real and available: the exact synthesized cell list and each cell's physical
width from the sky130 HD liberty (width = cell_area / row_height, row_height =
2.72 um).  We pack those real cells into rows at a stated core utilization to get
a genuine die x*y, emit a real .gds (cell bounding boxes), and render a
layout-style SVG.  Colored by CELL FUNCTION (not layer) to tell the comparison
story.  This is a placement/floorplan ESTIMATE; absolute x/y scale with the
utilization assumption, but the Design2/Design1 RATIO does not.
"""
import re, os, math, csv

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(HERE)
SYNTH  = os.path.join(ROOT, "synth")
REPORT = os.path.join(ROOT, "report")
LIB    = os.path.join(SYNTH, "sky130_fd_sc_hd__tt_025C_1v80.lib")

ROW_H = 2.72          # sky130_fd_sc_hd site height (um)
UTIL  = 0.65          # target core utilization (stated assumption)

# cell-function -> (label, dark-surface hue from the validated categorical set)
CATS = {
    "ff":    ("Flip-flops",       "#3987e5"),   # blue
    "arith": ("Adder (xor/maj)",  "#199e70"),   # aqua
    "mux":   ("Multiplexers",     "#c98500"),   # yellow
    "logic": ("Logic (aoi/nand)", "#9085e9"),   # violet
    "buf":   ("Clk / buf / iso",  "#d95926"),   # orange
}
CAT_ORDER = ["ff", "arith", "mux", "logic", "buf"]

def category(cell):
    n = cell.replace("sky130_fd_sc_hd__", "")
    if n.startswith(("df", "sdf", "edf")):                      return "ff"
    if n.startswith(("maj3", "xor", "xnor", "a2bb2", "fa", "ha", "fah")): return "arith"
    if n.startswith("mux"):                                     return "mux"
    if n.startswith(("clk", "lpflow", "buf", "conb", "dly")) or "iso" in n: return "buf"
    return "logic"

def parse_cell_areas(path):
    cell_re = re.compile(r'^\s*cell\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)')
    area_re = re.compile(r'^\s*area\s*:\s*([0-9.eE+-]+)')
    areas, cur, depth = {}, None, 0
    for line in open(path):
        m = cell_re.match(line)
        if m and depth == 1: cur = m.group(1)
        a = area_re.match(line)
        if a and cur and cur not in areas: areas[cur] = float(a.group(1))
        depth += line.count("{"); depth -= line.count("}")
        if cur and depth <= 1: cur = None
    return areas

def parse_netlist(path):
    inst_re = re.compile(r'^\s*(sky130_fd_sc_hd__\w+)\s+\S+\s*\(')
    insts = []
    for line in open(path):
        m = inst_re.match(line)
        if m: insts.append(m.group(1))
    return insts

def place(insts, areas):
    """Row-pack real cells; return die x,y and list of placed rects (um)."""
    cells = [(c, areas[c] / ROW_H, category(c)) for c in insts]  # (name,width,cat)
    total_w  = sum(w for _, w, _ in cells)
    cell_area = sum(areas[c] for c in insts)
    die_area = cell_area / UTIL
    nrows = max(1, round(math.sqrt(die_area) / ROW_H))
    die_y = nrows * ROW_H
    per_row_cell_w = total_w / nrows
    die_x = per_row_cell_w / UTIL                 # -> each row ~UTIL full
    # pack sequentially into rows; spread x across full die width so the
    # (1-UTIL) whitespace is distributed as inter-cell gaps (like real placement)
    spread = die_x / per_row_cell_w                # = 1/UTIL
    rects, x, row = [], 0.0, 0
    for name, w, cat in cells:
        if x + w > per_row_cell_w and x > 0:
            row += 1; x = 0.0
            if row >= nrows: row = nrows - 1      # spill guard
        y = die_y - (row + 1) * ROW_H
        rects.append((x * spread, y, w, ROW_H, cat))
        x += w
    return dict(die_x=die_x, die_y=die_y, die_area=die_x * die_y,
                cell_area=cell_area, nrows=nrows, rects=rects)

# ---------------------------------------------------------------------------
def write_gds(path, top, pl):
    import gdstk
    lib = gdstk.Library()
    cellsdef = lib.new_cell(top)
    layer_of = {c: i + 1 for i, c in enumerate(CAT_ORDER)}
    for (x, y, w, h, cat) in pl["rects"]:
        cellsdef.add(gdstk.rectangle((x, y), (x + w, y + h), layer=layer_of[cat]))
    # die boundary on layer 0
    cellsdef.add(gdstk.rectangle((0, 0), (pl["die_x"], pl["die_y"]), layer=0))
    lib.write_gds(path)

# ---------------------------------------------------------------------------
def svg(title, pl, ref_x, ref_y, ref_label=None):
    """Render at a COMMON scale set by (ref_x, ref_y) so the two dies are directly
    comparable in size.  A smaller die (Design 2) sits inside the reference
    footprint frame (Design 1's bounding box)."""
    W = 520.0
    scale = W / ref_x                       # common px/µm, fixed by the reference die
    Href  = ref_y * scale                   # reference die height in px
    dw = pl["die_x"] * scale                # this die's width  in px
    dh = pl["die_y"] * scale                # this die's height in px
    padL, padR, padT, padB = 62, 24, 40, 64
    fw, fh = padL + W + padR, padT + Href + padB
    S = []
    S.append('<svg viewBox="0 0 %.0f %.0f" width="100%%" '
             'xmlns="http://www.w3.org/2000/svg" font-family="system-ui,-apple-system,Segoe UI,sans-serif">'
             % (fw, fh))
    S.append('<rect x="0" y="0" width="%.0f" height="%.0f" rx="10" fill="#141413"/>' % (fw, fh))
    S.append('<text x="%.0f" y="24" fill="#ffffff" font-size="14" font-weight="600">%s</text>'
             % (padL, title))
    ox, oy = padL, padT
    # reference footprint frame (Design 1's die), dashed, drawn behind
    if ref_label:
        S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" '
                 'stroke="#57564f" stroke-width="1" stroke-dasharray="4 4"/>'
                 % (ox, oy, W, Href))
        S.append('<text x="%.1f" y="%.1f" fill="#8a897f" font-size="10.5" text-anchor="end">%s</text>'
                 % (ox + W, oy + Href + 13, ref_label))
    # this die core (top-left anchored inside the reference frame)
    S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#1f1f1d" '
             'stroke="#3a3a37" stroke-width="1"/>' % (ox, oy, dw, dh))
    for (x, y, w, h, cat) in pl["rects"]:
        rx = ox + x * scale; ry = oy + y * scale
        rw = max(0.5, w * scale - 0.3); rh = max(0.6, h * scale - 0.4)
        S.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>'
                 % (rx, ry, rw, rh, CATS[cat][1]))
    # x dimension along THIS die's actual width
    yb = oy + Href + 22
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c3c2b7" stroke-width="1"/>'
             % (ox, yb, ox + dw, yb))
    for xx in (ox, ox + dw):
        S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c3c2b7" stroke-width="1"/>'
                 % (xx, yb - 4, xx, yb + 4))
    S.append('<text x="%.1f" y="%.1f" fill="#e8e8e2" font-size="12.5" text-anchor="middle" '
             'font-weight="600">x = %.1f µm</text>' % (ox + dw / 2, yb + 18, pl["die_x"]))
    # y dimension along THIS die's actual height
    xl = ox - 16
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c3c2b7" stroke-width="1"/>'
             % (xl, oy, xl, oy + dh))
    for yy in (oy, oy + dh):
        S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c3c2b7" stroke-width="1"/>'
                 % (xl - 4, yy, xl + 4, yy))
    S.append('<text x="%.1f" y="%.1f" fill="#e8e8e2" font-size="12.5" text-anchor="middle" '
             'font-weight="600" transform="rotate(-90 %.1f %.1f)">y = %.1f µm</text>'
             % (xl - 8, oy + dh / 2, xl - 8, oy + dh / 2, pl["die_y"]))
    # caption
    S.append('<text x="%.0f" y="%.0f" fill="#898781" font-size="11">%d rows · die %.0f × %.0f = %.0f µm² '
             '· cells %.0f µm² @ %.0f%% util</text>'
             % (padL, fh - 8, pl["nrows"], pl["die_x"], pl["die_y"], pl["die_area"],
                pl["cell_area"], UTIL * 100))
    S.append('</svg>')
    return "\n".join(S)

# ---------------------------------------------------------------------------
def read_k():
    m = re.search(r'\bK=(\d+)\b', open(os.path.join(REPORT, "model_accuracy.txt")).read())
    return int(m.group(1)) if m else 1

def main():
    areas = parse_cell_areas(LIB)
    kval = read_k()
    designs = [
        ("Design 1 — mult_detector (baseline)", "mult_detector", "mult_detector_netlist.v"),
        ("Design 2 — log_detector (K=%d)" % kval, "log_detector",  "log_detector_netlist.v"),
    ]
    # place both first, then render both at Design 1's common scale
    placed = []
    for title, top, netl in designs:
        insts = parse_netlist(os.path.join(SYNTH, netl))
        pl = place(insts, areas)
        write_gds(os.path.join(SYNTH, top + ".gds"), top, pl)
        placed.append((title, top, pl))
    ref_x = placed[0][2]["die_x"]; ref_y = placed[0][2]["die_y"]   # Design 1 is the reference
    rows = []
    for idx, (title, top, pl) in enumerate(placed):
        ref_label = None if idx == 0 else "Design 1 footprint (same scale)"
        open(os.path.join(REPORT, top + "_layout.svg"), "w").write(
            svg(title, pl, ref_x, ref_y, ref_label))
        rows.append((top, pl))
        print("%-16s die %.1f x %.1f um  (%.0f um2 die, %.1f um2 cells, %d rows) -> %s.gds"
              % (top, pl["die_x"], pl["die_y"], pl["die_area"], pl["cell_area"], pl["nrows"], top))
    with open(os.path.join(REPORT, "floorplan.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["design", "die_x_um", "die_y_um", "die_area_um2",
                    "cell_area_um2", "utilization", "rows"])
        for top, pl in rows:
            w.writerow([top, "%.2f" % pl["die_x"], "%.2f" % pl["die_y"],
                        "%.1f" % pl["die_area"], "%.1f" % pl["cell_area"],
                        "%.2f" % UTIL, pl["nrows"]])
    b, l = rows[0][1], rows[1][1]
    print("die-area ratio log/mult = %.3f  (x %.3f, y %.3f)"
          % (l["die_area"]/b["die_area"], l["die_x"]/b["die_x"], l["die_y"]/b["die_y"]))
    print("wrote report/{mult,log}_detector_layout.svg, floorplan.csv, synth/*.gds")

if __name__ == "__main__":
    main()
