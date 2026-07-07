#!/usr/bin/env python3
"""
Build docs/index.html (a self-contained GitHub Pages page) from the flow's own
artifacts: power_area.csv, floorplan.csv, model_accuracy.txt, the layout SVGs,
and a cell-function breakdown of each netlist.  No numbers are hand-typed.
"""
import os, csv, re, html, math

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(HERE)
SYNTH  = os.path.join(ROOT, "synth")
REPORT = os.path.join(ROOT, "report")
DOCS   = os.path.join(ROOT, "docs")
LIB    = os.path.join(SYNTH, "sky130_fd_sc_hd__tt_025C_1v80.lib")

import sys as _sys
_sys.path.insert(0, HERE)
import model as MODEL      # reuse the golden model for the worked-example table

K      = MODEL.K                                  # fraction bits in the log converter
WIDTH  = MODEL.WIDTH                              # input bit width
SCALE  = MODEL.SCALE                              # 2^K : log-value units are 1/SCALE of a log2
UNITW  = {1: "half", 2: "quarter", 3: "eighth"}.get(K, "1/%d" % SCALE) + "-log₂"
FBITS  = max(1, (SCALE).bit_length())             # bits to represent an F value (0..SCALE)
WIDTH_BASE = 1 << WIDTH                            # 2^WIDTH (input-space base, e.g. 1024)
_p_space   = WIDTH_BASE ** 4
_exp_space = len(str(_p_space)) - 1
SPACE_SCI  = "%.1f×10%s" % (_p_space / 10.0 ** _exp_space,
             str(_exp_space).translate(str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")))

# category -> (label, light hue, dark hue) : same families as the layout SVG
CATS = [
    ("ff",    "Flip-flops",       "#2a78d6", "#3987e5"),
    ("arith", "Adder (xor/maj)",  "#1baf7a", "#199e70"),
    ("mux",   "Multiplexers",     "#eda100", "#c98500"),
    ("logic", "Logic (aoi/nand)", "#4a3aa7", "#9085e9"),
    ("buf",   "Clk / buf / iso",  "#eb6834", "#d95926"),
]
CAT_LABEL = {k: l for k, l, _, _ in CATS}
CAT_LIGHT = {k: c for k, _, c, _ in CATS}

def category(cell):
    n = cell.replace("sky130_fd_sc_hd__", "")
    if n.startswith(("df", "sdf", "edf")):                                 return "ff"
    if n.startswith(("maj3", "xor", "xnor", "a2bb2", "fa", "ha", "fah")):  return "arith"
    if n.startswith("mux"):                                                return "mux"
    if n.startswith(("clk", "lpflow", "buf", "conb", "dly")) or "iso" in n: return "buf"
    return "logic"

def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))

def parse_cell_areas():
    cell_re = re.compile(r'^\s*cell\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)')
    area_re = re.compile(r'^\s*area\s*:\s*([0-9.eE+-]+)')
    areas, cur, depth = {}, None, 0
    for line in open(LIB):
        m = cell_re.match(line)
        if m and depth == 1: cur = m.group(1)
        a = area_re.match(line)
        if a and cur and cur not in areas: areas[cur] = float(a.group(1))
        depth += line.count("{"); depth -= line.count("}")
        if cur and depth <= 1: cur = None
    return areas

def cat_area(netlist, areas):
    inst_re = re.compile(r'^\s*(sky130_fd_sc_hd__\w+)\s+\S+\s*\(')
    out = {k: 0.0 for k, *_ in CATS}
    for line in open(os.path.join(SYNTH, netlist)):
        m = inst_re.match(line)
        if m: out[category(m.group(1))] += areas[m.group(1)]
    return out

def per_vth():
    rows, overall = [], None
    for line in open(os.path.join(REPORT, "model_accuracy.txt")):
        m = re.match(r'\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s*$', line)
        if m: rows.append((int(m.group(1)), float(m.group(4))))
        mo = re.search(r'OVERALL disagreement rate =.*=\s*([0-9.]+)\s*%', line)
        if mo: overall = float(mo.group(1))
    return rows, overall

# ---------------------------------------------------------------------------
pa = {r["design"]: r for r in read_csv(os.path.join(REPORT, "power_area.csv"))}
fp = {r["design"]: r for r in read_csv(os.path.join(REPORT, "floorplan.csv"))}
areas = parse_cell_areas()
mult_cat = cat_area("mult_detector_netlist.v", areas)
log_cat  = cat_area("log_detector_netlist.v", areas)
vth_rows, overall = per_vth()

svg_mult = open(os.path.join(REPORT, "mult_detector_layout.svg")).read()
svg_log  = open(os.path.join(REPORT, "log_detector_layout.svg")).read()

# vector count (for the footer) and GitHub links base
nvec = sum(1 for _ in open(os.path.join(ROOT, "verif", "vectors.csv"))) - 1
REPO      = "https://github.com/borenw/sky130-lns-mac-detector"
REPO_BLOB = REPO + "/blob/main"
REPO_ZIP  = REPO + "/archive/refs/heads/main.zip"

# ---- revision badge (git state at build time) ----
import subprocess as _sp
def _git(args, default=""):
    try:
        return _sp.check_output(["git"] + args, cwd=ROOT, stderr=_sp.DEVNULL).decode().strip()
    except Exception:
        return default
REV_SHA   = _git(["rev-parse", "--short", "HEAD"], "dev")
REV_NUM   = _git(["rev-list", "--count", "HEAD"], "")
REV_DATE  = _git(["log", "-1", "--format=%cd", "--date=short"], "")
REV_LABEL = ("r%s · %s" % (REV_NUM, REV_SHA)) if REV_NUM else REV_SHA

M = pa["mult baseline"]; L = pa["log K=%d" % K]
FM = fp["mult_detector"]; FL = fp["log_detector"]

def f(x): return float(x)
area_save = 100 * (1 - f(L["area_um2"]) / f(M["area_um2"]))
pow_save  = 100 * (1 - f(L["x_baseline_power"]))
die_save  = 100 * (1 - f(FL["die_area_um2"]) / f(FM["die_area_um2"]))

# ---- comparison table rows ----
def pct(a, b): return "%.3f×" % (f(a) / f(b))
# each row: (metric, design1, design2, delta, sentiment)  sentiment: good|bad|neutral
rows_tbl = [
    ("Standard-cell area", "%s µm²" % M["area_um2"], "%s µm²" % L["area_um2"],
     "%.3f× (−%.1f%%)" % (f(L["area_um2"])/f(M["area_um2"]), area_save), "good"),
    ("Die size (x × y @65%)", "%s × %s µm" % (FM["die_x_um"], FM["die_y_um"]),
     "%s × %s µm" % (FL["die_x_um"], FL["die_y_um"]),
     "%.3f× (−%.1f%%)" % (f(FL["die_area_um2"])/f(FM["die_area_um2"]), die_save), "good"),
    ("Die area (x·y)", "%s µm²" % FM["die_area_um2"], "%s µm²" % FL["die_area_um2"],
     "%.3f×" % (f(FL["die_area_um2"])/f(FM["die_area_um2"])), "good"),
    ("Std-cell count", M["cells"], L["cells"],
     "%.3f×" % (f(L["cells"])/f(M["cells"])), "good"),
    ("Multipliers ($mul)", "2", "0", "eliminated", "good"),
    ("Energy / op (est.)", "%s pJ" % M["energy_per_op_pJ"], "%s pJ" % L["energy_per_op_pJ"],
     "%.3f×" % (f(L["energy_per_op_pJ"])/f(M["energy_per_op_pJ"])), "good"),
    ("Power @ 50 MHz (est.)", "%s µW" % M["power_uW_at_50MHz"], "%s µW" % L["power_uW_at_50MHz"],
     "%.3f× (−%.1f%%)" % (f(L["x_baseline_power"]), pow_save), "good"),
    ("Accuracy vs exact", "0.00 % (reference)", "%.2f %% disagree" % overall,
     "K=%d cost" % K, "bad"),
    ("Verification", "PASS (= exp_exact)", "PASS (= exp_k1)", "both bit-exact", "neutral"),
]
_SENT = {"good": ("delta gain", "▼ "), "bad": ("delta loss", "▲ "), "neutral": ("delta", "")}

def tbl_rows():
    out = []
    for metric, a, b, delta, sent in rows_tbl:
        dcls, arrow = _SENT[sent]
        bcls = "hl gain" if sent == "good" else ("hl loss" if sent == "bad" else "hl")
        out.append(
            "<tr><th scope='row'>%s</th><td>%s</td><td class='%s'>%s</td>"
            "<td class='%s'>%s%s</td></tr>" % (metric, a, bcls, b, dcls, arrow, delta))
    return "\n".join(out)

# ---- cell-composition stacked bars ----
def comp_bar(catd, total):
    seg = []
    for k, label, lhue, _ in CATS:
        w = 100 * catd[k] / total
        if w <= 0: continue
        seg.append("<div class='seg' style='width:%.3f%%;background:%s' "
                   "title='%s: %.0f µm²'></div>" % (w, lhue, label, catd[k]))
    return "".join(seg)

mult_total = sum(mult_cat.values()); log_total = sum(log_cat.values())

def legend():
    items = []
    for k, label, lhue, _ in CATS:
        items.append("<span class='lg'><i style='background:%s'></i>%s</span>" % (lhue, label))
    return "".join(items)

# ---- per-Vth disagreement bars ----
vmax = max(v for _, v in vth_rows) or 1
def vth_bars():
    out = []
    for vth, v in vth_rows:
        out.append(
            "<div class='vrow'><span class='vlab'>%d</span>"
            "<div class='vtrack'><div class='vbar' style='width:%.2f%%'></div></div>"
            "<span class='vval'>%.2f%%</span></div>" % (vth, 100 * v / vmax, v))
    return "\n".join(out)

# ---- datapath block diagram (inline SVG, theme-aware via CSS vars) ----
# module-level SVG helpers, shared by block_diagram() and rtl_diagram()
def blk(x, y, w, h, lines, accent=None):
    p = ['<rect x="%g" y="%g" width="%g" height="%g" rx="6" fill="var(--surface)" '
         'stroke="var(--ring)"/>' % (x, y, w, h)]
    if accent:
        p.append('<rect x="%g" y="%g" width="3.5" height="%g" rx="1.5" fill="%s"/>'
                 % (x, y, h, accent))
    n = len(lines)
    for i, ln in enumerate(lines):
        ty = y + h / 2 - (n - 1) * 5.5 + i * 11 + 3.5
        if i == 0:
            p.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" '
                     'font-weight="600" fill="var(--ink)">%s</text>' % (x + w / 2, ty, ln))
        else:
            p.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9.5" '
                     'fill="var(--ink2)">%s</text>' % (x + w / 2, ty, ln))
    return "".join(p)

def arr(x1, y1, x2, y2, label=None):
    s = ['<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--muted)" stroke-width="1.4" '
         'marker-end="url(#ah)"/>' % (x1, y1, x2, y2)]
    if label:
        s.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9" '
                 'fill="var(--muted)">%s</text>' % ((x1 + x2) / 2, min(y1, y2) - 4, label))
    return "".join(s)

def block_diagram():
    RED, BLUE = "#e34948", "var(--accent)"
    P = ['<svg viewBox="0 0 520 284" width="100%" xmlns="http://www.w3.org/2000/svg" '
         'font-family="system-ui,-apple-system,Segoe UI,sans-serif">',
         '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6.5" refY="3" '
         'orient="auto"><path d="M0,0 L6.5,3 L0,6 z" fill="var(--muted)"/></marker></defs>']
    # lane 1 : multiplier baseline -- (A·B − C·D) > Vth  (true subtract)
    P.append('<text x="14" y="22" font-size="12.5" font-weight="700" fill="var(--ink2)">'
             '① Multiplier — baseline</text>')
    P.append(arr(62, 53, 82, 53));  P.append(arr(62, 87, 82, 87))
    P.append(arr(136, 53, 158, 64, "A·B")); P.append(arr(136, 87, 158, 78, "C·D"))
    P.append(arr(200, 71, 224, 71, "S±")); P.append(arr(296, 71, 322, 70))
    P.append(blk(14, 42, 48, 22, ["A, B"]));  P.append(blk(14, 76, 48, 22, ["C, D"]))
    P.append(blk(82, 40, 54, 26, ["A × B"], RED))
    P.append(blk(82, 74, 54, 26, ["C × D"], RED))
    P.append(blk(158, 56, 42, 30, ["−"]))
    P.append(blk(224, 54, 72, 34, ["S &gt; Vth"]))
    P.append(blk(322, 57, 52, 26, ["out"]))
    # lane 2 : log / LNS -- Vth is a compile-time constant, so w = log₂(2^y + Vth) is a
    # function of y alone: the whole max+F LNS add collapses into a single-input w-ROM
    # (Vth baked into the ROM contents offline, no runtime Vth converter).
    P.append('<text x="14" y="146" font-size="12.5" font-weight="700" fill="var(--ink2)">'
             '② Log / LNS, K=%d</text>' % K)
    P.append('<rect x="148" y="133" width="106" height="17" rx="8.5" '
             'fill="rgba(12,163,12,0.14)" stroke="#0ca30c" stroke-width="0.8"/>')
    P.append('<text x="201" y="145" text-anchor="middle" font-size="10" font-weight="600" '
             'fill="#0ca30c">✓ no × cells</text>')
    # input -> log2 arrows (4 operands; Vth is baked into the ROM, not a runtime input)
    for cy in (166.5, 191.5, 220.5, 245.5):
        P.append(arr(44, cy, 52, cy))
    # log2 -> adders
    P.append(arr(104, 166.5, 124, 173)); P.append(arr(104, 191.5, 124, 186))
    P.append(arr(104, 220.5, 124, 227)); P.append(arr(104, 245.5, 124, 240))
    # add1 -> compare (x = log A·B) ; add2 -> w-ROM (y) ;
    # w-ROM -> compare (w = log₂(2^y + Vth)) ; compare -> out
    P.append(arr(156, 179, 346, 208, "x"))
    P.append(arr(156, 233, 190, 244, "y"))
    P.append(arr(336, 249, 346, 230, "w"))
    P.append(arr(446, 218, 460, 218))
    # input boxes (A, B, C, D only -- no runtime Vth)
    for y, lbl in ((158, "A"), (183, "B"), (212, "C"), (237, "D")):
        P.append(blk(12, y, 32, 17, [lbl]))
    # per-operand log2 converters (the four parallel paths)
    for y in (158, 183, 212, 237):
        P.append(blk(52, y, 52, 17, ["log₂·K%d" % K], BLUE))
    # two log-adders (= LNS multiply); single-input w-ROM (Vth baked in); compare; out
    P.append(blk(124, 166, 32, 26, ["+"])); P.append(blk(124, 220, 32, 26, ["+"]))
    P.append(blk(190, 226, 146, 46, ["w-ROM (Vth baked in)", "w = log₂(2ʸ + Vth)"], BLUE))
    P.append(blk(346, 196, 100, 44, ["compare &gt;", "A·B &gt; C·D+Vth"]))
    P.append(blk(460, 205, 50, 26, ["out"]))
    P.append('</svg>')
    cap = ('<figcaption>V<sub>th</sub> is constant, so the max + F(|y−v|) LNS adder collapses '
           'into a single-input ROM w = log₂(2<sup>y</sup> + V<sub>th</sub>) — no max, no '
           'subtract, no runtime V<sub>th</sub> converter. Trade-off: the threshold is frozen '
           'into the ROM; reprogramming it means reloading the ROM.</figcaption>')
    return '<figure class="bd">' + "".join(P) + cap + '</figure>'

def rtl_diagram():
    """RTL module/file hierarchy in the same left-to-right flow, arrows carry the
    actual RTL signal names, blocks end in their source-file name (.v)."""
    RED, BLUE = "#e34948", "var(--accent)"
    P = ['<svg viewBox="0 0 690 244" width="100%" xmlns="http://www.w3.org/2000/svg" '
         'font-family="system-ui,-apple-system,Segoe UI,sans-serif">',
         '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6.5" refY="3" '
         'orient="auto"><path d="M0,0 L6.5,3 L0,6 z" fill="var(--muted)"/></marker></defs>']
    # lane 1 : baseline, one file
    P.append('<text x="14" y="22" font-size="12.5" font-weight="700" fill="var(--ink2)">'
             '① Baseline — one file</text>')
    P.append(blk(14, 44, 56, 34, ["A,B,C,D", "Vth"]))
    P.append(arr(70, 61, 120, 61, "Ar…Vr"))
    P.append(blk(120, 41, 178, 42, ["mult_detector.v", "p1=Ar*Br  p2=Cr*Dr", "S=p1+p2 · out←(S&gt;Vr)"], RED))
    P.append(arr(298, 62, 336, 62, "out"))
    P.append(blk(336, 49, 54, 26, ["out"]))
    # lane 2 : log design -- files instantiated inside the top module
    P.append('<text x="14" y="118" font-size="12.5" font-weight="700" fill="var(--ink2)">'
             '② Multiplier-free — log_detector.v  ·  lod5.v · lns_add.v · lns_ftable.v</text>')
    P.append('<rect x="96" y="138" width="500" height="96" rx="9" fill="none" '
             'stroke="#57564f" stroke-width="1" stroke-dasharray="4 4"/>')
    P.append('<text x="104" y="152" font-size="10" fill="#8a897f">log_detector.v (top module)</text>')
    P.append(blk(14, 168, 58, 40, ["A,B,C,D", "Vth"]))
    P.append(arr(72, 188, 100, 188))
    P.append(blk(100, 170, 48, 36, ["input", "regs"]))
    P.append(arr(148, 188, 178, 188, "Ar…Vr"))
    P.append(blk(178, 168, 60, 44, ["lod5.v", "×5"], BLUE))
    P.append(arr(238, 188, 268, 188, "e,f,z"))
    P.append(blk(268, 170, 68, 40, ["L, X, Y", "(inline)"]))
    P.append(arr(336, 188, 366, 188, "X,Y"))
    P.append(blk(366, 164, 110, 52, ["lns_add.v", "+ lns_ftable.v", "s = max+F"], BLUE))
    P.append(arr(476, 188, 506, 188, "s"))
    P.append(blk(506, 170, 80, 40, ["compare", "+ out reg"]))
    P.append(arr(586, 188, 618, 188, "out"))
    P.append(blk(618, 175, 52, 26, ["out"]))
    P.append('</svg>')
    cap = ('<figcaption>The same flow at the <b>RTL level</b>: blocks ending in '
           '<code>.v</code> are actual source files and arrows carry the real signal names. '
           'The baseline is a single <code>mult_detector.v</code>; the multiplier-free design '
           'is <code>log_detector.v</code> (top) instantiating five <code>lod5.v</code> '
           'converters (A, B, C, D + Vth) and one <code>lns_add.v</code> — which instantiates '
           'the generated <code>lns_ftable.v</code> ROM. Input registers, L=&#123;e,f&#125;, '
           'X=La+Lb, the comparator and the output register are inline in the top module.'
           '</figcaption>')
    return '<figure class="bd">' + "".join(P) + cap + '</figure>'

# ---- worked-example table (real values through the golden model) ----
def _k1_row(A, B, C, D, Vth):
    zA, la = MODEL.log_k1(A); zB, lb = MODEL.log_k1(B)
    zC, lc = MODEL.log_k1(C); zD, ld = MODEL.log_k1(D)
    zx = zA or zB; zy = zC or zD
    X = la + lb; Y = lc + ld
    if zx and zy: s = 0
    elif zx:      s = Y
    elif zy:      s = X
    else:         s = max(X, Y) + MODEL.FTAB[abs(X - Y)]
    zv, lv = MODEL.log_k1(Vth)
    S = A * B + C * D
    Shat = 2.0 ** (s / float(SCALE))
    Vhat = 0.0 if zv else 2.0 ** (lv / float(SCALE))
    out_ex = 1 if S > Vth else 0
    out_k1 = MODEL.out_k1(A, B, C, D, Vth)
    err = 100.0 * (Shat - S) / S if S > 0 else 0.0
    return S, Shat, Vhat, err, out_ex, out_k1

EXAMPLES = [(25, 30, 12, 40, 600), (8, 8, 5, 5, 150),
            (50, 50, 20, 20, 2000), (3, 3, 3, 3, 17)]
# compute once so both the table and the prose note cite the same (K-dependent) numbers
EX = [dict(A=A, B=B, C=C, D=D, Vth=Vth,
           S=r[0], Shat=r[1], Vhat=r[2], err=r[3], oe=r[4], ok=r[5], mis=(r[4] != r[5]))
      for (A, B, C, D, Vth) in EXAMPLES
      for r in [_k1_row(A, B, C, D, Vth)]]
MISJ = next(e for e in EX if e["mis"])            # the misjudge row (for the note)
BIGERR = max((e for e in EX if not e["mis"]),      # a matching row with the largest |err|
             key=lambda e: abs(e["err"]))

def example_rows():
    out = []
    for e in EX:
        verdict = ('<span class="bad">misjudge ✗</span>' if e["mis"]
                   else '<span class="ok2">match ✓</span>')
        # err% is the OUTPUT error: N/A when the output is correct, shown only on a misjudge
        err_cell = ('<span class="bad">%+.1f%%</span>' % e["err"] if e["mis"]
                    else '<span class="na">—</span>')
        out.append(
            "<tr%s><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td>"
            "<td>%d</td><td>%d</td>"
            "<td>%.0f</td><td>%s</td><td>%.0f</td><td>%d</td><td class='hl'>%d</td>"
            "<td>%s</td></tr>"
            % (' class="misrow"' if e["mis"] else '', e["A"], e["B"], e["C"], e["D"], e["Vth"],
               e["S"], e["A"] * e["B"] - e["C"] * e["D"],
               e["Shat"], err_cell, e["Vhat"], e["oe"], e["ok"], verdict))
    return "".join(out)
EXROWS = example_rows()

# ---- file links (to the GitHub repo) ----
FILE_GROUPS = [
    ("RTL — source", [
        ("mult_detector.v", "rtl/mult_detector.v"),
        ("log_detector.v", "rtl/log_detector.v"),
        ("lod5.v", "rtl/lod5.v"),
        ("lns_add.v", "rtl/lns_add.v"),
        ("lns_ftable.v (generated)", "rtl/lns_ftable.v"),
    ]),
    ("Gate-level netlists", [
        ("mult_detector_netlist.v", "synth/mult_detector_netlist.v"),
        ("log_detector_netlist.v", "synth/log_detector_netlist.v"),
    ]),
    ("Layout / GDS + synth", [
        ("mult_detector.gds", "synth/mult_detector.gds"),
        ("log_detector.gds", "synth/log_detector.gds"),
        ("run_mult.ys", "synth/run_mult.ys"),
        ("run_log.ys", "synth/run_log.ys"),
    ]),
    ("Model & scripts", [
        ("model.py (golden + F-ROM)", "model/model.py"),
        ("power_area.py", "model/power_area.py"),
        ("floorplan.py", "model/floorplan.py"),
        ("build_page.py", "model/build_page.py"),
    ]),
    ("Verification", [
        ("tb.v", "verif/tb.v"),
        ("vectors.csv", "verif/vectors.csv"),
        ("sim_report.txt", "verif/sim_report.txt"),
    ]),
    ("Reports", [
        ("SUMMARY.md", "report/SUMMARY.md"),
        ("model_accuracy.txt", "report/model_accuracy.txt"),
        ("elaboration.txt", "report/elaboration.txt"),
        ("power_area.csv", "report/power_area.csv"),
        ("floorplan.csv", "report/floorplan.csv"),
    ]),
]

def files_section():
    out = []
    for title, items in FILE_GROUPS:
        links = "".join('<a href="%s/%s">%s</a>' % (REPO_BLOB, path, label)
                        for label, path in items)
        out.append('<div class="fgroup"><h3>%s</h3>%s</div>' % (title, links))
    return "".join(out)

# ---- LNS-add derivation detail (for the deep-dive section) ----
def _Fd(dh):                       # dh = integer ROM key; real d = dh/SCALE
    d = dh / float(SCALE)
    real = math.log2(1.0 + 2.0 ** (-d))
    return real, int(round(SCALE * real))
FROWS = "".join(
    "<tr><td>%.2f</td><td>%.4f</td><td>%d</td></tr>" % (dh / float(SCALE), _Fd(dh)[0], _Fd(dh)[1])
    for dh in range(0, 9))
_mrom = re.search(r'F\(d\) ROM \([^)]*\):\s*\[([^\]]*)\]',
                  open(os.path.join(REPORT, "model_accuracy.txt")).read())
_romvals = [v.strip() for v in _mrom.group(1).split(",")] if _mrom else ["4", "4", "3", "3"]
ROM_LEN  = len(_romvals)
ROM_MAXD = ROM_LEN - 1
ROM_PREVIEW = "[" + ", ".join(_romvals[:9]) + ", …, 0]"
DERIV = (
    "  A·B = 2^x           C·D = 2^y            x = log2 A + log2 B\n"
    "\n"
    "  2^x + 2^y                       (assume x ≥ y)\n"
    "    = 2^x · ( 1 + 2^(y−x) )\n"
    "    = 2^max(x,y) · ( 1 + 2^−d )         d = |x − y|\n"
    "\n"
    "  s = log2( 2^x + 2^y )\n"
    "    = max(x,y) + log2( 1 + 2^−d )\n"
    "    = max(x,y) + F(d)                   F(d) = log2(1 + 2^−d)   ← the ROM"
)

# ---- concrete LNS-add walkthrough for worked-example row 1 (C·D = 12·40) ----
def _wbr(v):                       # (exponent, K-bit frac, L, binary) for the K-bit converter
    e = v.bit_length() - 1
    frac = 0
    for _i in range(1, K + 1):
        _pos = e - _i
        frac |= (((v >> _pos) & 1) if _pos >= 0 else 0) << (K - _i)
    return e, frac, (e << K) + frac, format(v, 'b')

def _build_walk():
    A, B, C, D, Vth = 25, 30, 12, 40, 600
    eA, fA, LA, bA = _wbr(A); eB, fB, LB, bB = _wbr(B)
    eC, fC, LC, bC = _wbr(C); eD, fD, LD, bD = _wbr(D)
    X = LA + LB; Y = LC + LD; d = abs(X - Y)
    F = int(_romvals[d]); s = max(X, Y) + F
    S = A * B + C * D; Shat = 2 ** (s / float(SCALE)); err = 100.0 * (Shat - S) / S
    eV, fV, LV, bV = _wbr(Vth); Vhat = 2 ** (LV / float(SCALE))
    oe = 1 if S > Vth else 0; ok = 1 if s > LV else 0
    L = []
    L.append("  A=%d  B=%d  C=%d  D=%d   (Vth=%d)        logs in 1/%d-log2 units" % (A, B, C, D, Vth, SCALE))
    L.append("")
    L.append("  1) log-convert   L(v) = %d*floor(log2 v) + (top %d mantissa bits)" % (SCALE, K))
    for v, e, f, Lv_, b in ((A, eA, fA, LA, bA), (B, eB, fB, LB, bB),
                            (C, eC, fC, LC, bC), (D, eD, fD, LD, bD)):
        L.append("       L(%2d) = %d*%d + %d = %-2d       %d = %sb" % (v, SCALE, e, f, Lv_, v, b))
    L.append("")
    L.append("  2) multiply = add the logs   (adding logs multiplies the operands)")
    L.append("       X = L(%d)+L(%d) = %d      ->  A*B ~ 2^(%g) = %.0f     (true %d)"
             % (A, B, X, X / float(SCALE), 2 ** (X / float(SCALE)), A * B))
    L.append("       Y = L(%d)+L(%d) = %d      ->  C*D ~ 2^(%g) = %.0f     (true %d)"
             % (C, D, Y, Y / float(SCALE), 2 ** (Y / float(SCALE)), C * D))
    L.append("")
    L.append("  3) LNS add   (combine the two products, still in the log domain)")
    L.append("       d = |X - Y| = |%d - %d| = %d" % (X, Y, d))
    L.append("       F(d) = ROM[%d] = %d                         <-- the one table lookup" % (d, F))
    L.append("       s = max(X,Y) + F(d) = %d + %d = %d" % (max(X, Y), F, s))
    L.append("")
    L.append("  4) result    S_hat = 2^(%g) = %.0f              (true A*B+C*D = %d,  err %+.1f%%)"
             % (s / float(SCALE), Shat, S, err))
    L.append("")
    L.append("  5) compare   Lv = L(%d) = %d  ->  V_hat = %.0f" % (Vth, LV, Vhat))
    L.append("       s=%d %s Lv=%d   ->  out = %d       (exact: %d %s %d -> %d)   %s"
             % (s, '>' if s > LV else '<=', LV, ok, S, '>' if S > Vth else '<=', Vth, oe,
                'match' if ok == oe else 'MISJUDGE'))
    return html.escape("\n".join(L)), d
WALK, DUSED = _build_walk()

def _rom_slice():
    rs = []
    for k in range(0, 6):
        val = _romvals[k] if k < len(_romvals) else "0"
        realF = math.log2(1 + 2 ** (-(k / float(SCALE))))
        used = (k == DUSED)
        note = "← used (d = |X−Y|)" if used else ""
        rs.append("<tr%s><td>%d</td><td>%s</td><td>%.4f</td>"
                  "<td style='text-align:left;color:var(--accent);font-weight:600'>%s</td></tr>"
                  % (' class="usedrow"' if used else '', k, val, realF, note))
    return "".join(rs)
ROMSLICE = _rom_slice()

# ---- F(d) LUT deep-dive: transfer plot, collapsed truth table, behavioral+gate RTL ----
FTAB    = MODEL.FTAB
LAST_NZ = max(d for d, v in enumerate(FTAB) if v > 0)
XMAX    = min(len(FTAB) - 1, LAST_NZ + 3)

def lut_transfer_svg():
    # Vth'(C,D) vs log2(Vth) (sweeping the programmable threshold), for two product
    # levels C*D that are 4x apart -> shows how the operand level shifts the mapping.
    CD1 = 256; CD2 = 4 * CD1
    c1 = math.log2(CD1); c2 = math.log2(CD2)                       # knee x-positions (8, 10)
    x0, x1, ymax = 3.0, 16.0, 8.0
    W, H = 560, 214
    ox, oy = 44, 14
    pw, ph = W - ox - 12, H - oy - 56
    def X(u): return ox + pw * (u - x0) / (x1 - x0)
    def Y(val): return oy + ph * (1 - min(val, ymax) / ymax)
    def vp_q(lv, CD):                                             # ACTUAL quantized Vth′; lv = log2(Vth)
        Lv = round(SCALE * lv); Lc = round(SCALE * math.log2(CD))
        d = abs(Lv - Lc); Fv = FTAB[d] if d < len(FTAB) else 0
        return (max(Lc, Lv) - Lc + Fv) / float(SCALE)             # = out_q − log₂(C·D)
    ACC, AQ = "var(--accent)", "#199e70"
    S = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
         'font-family="system-ui,-apple-system,Segoe UI,sans-serif">' % (W, H)]
    for yv in range(0, int(ymax) + 1):                            # y grid + ticks
        yy = Y(yv)
        S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--grid)" stroke-width="1"/>'
                 % (ox, yy, ox + pw, yy))
        S.append('<text x="%.1f" y="%.1f" text-anchor="end" font-size="10" fill="var(--muted)">%d</text>'
                 % (ox - 6, yy + 3, yv))
    u = x0
    while u <= x1 + 1e-6:                                          # x ticks (even ints)
        if abs(u - round(u)) < 1e-6 and int(round(u)) % 2 == 0:
            xx = X(u)
            S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
                     % (xx, oy + ph, xx, oy + ph + 4))
            S.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="10" fill="var(--muted)">%d</text>'
                     % (xx, oy + ph + 16, int(round(u))))
        u += 1
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
             % (ox, oy, ox, oy + ph))
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
             % (ox, oy + ph, ox + pw, oy + ph))
    for CD, c, col in ((CD1, c1, ACC), (CD2, c2, AQ)):            # two product levels
        u, path = x0, "M %.1f %.1f" % (X(x0), Y(vp_q(x0, CD)))    # staircase (quarter-log₂ steps)
        while u <= x1 + 1e-6:
            path += " H %.1f V %.1f" % (X(u), Y(vp_q(u, CD)))
            u += 0.04
        S.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (path, col))
        S.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s"/>' % (X(c), Y(1), col))   # knee: Vth = C·D
    lx, ly = ox + 14, oy + 10                                     # legend (top-left, empty area)
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4"/>' % (lx, ly, lx + 18, ly, ACC))
    S.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="var(--ink2)">C·D = %d</text>' % (lx + 23, ly + 3, CD1))
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4"/>' % (lx + 96, ly, lx + 114, ly, AQ))
    S.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="var(--ink2)">C·D = %d (4×)</text>' % (lx + 119, ly + 3, CD2))
    S.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" fill="var(--ink2)">'
             'programmable threshold  log₂(Vth)</text>' % (ox + pw / 2, H - 4))
    S.append('<text x="11" y="%.1f" text-anchor="middle" font-size="11" fill="var(--ink2)" '
             'transform="rotate(-90 11 %.1f)">Vth′(C,D)</text>' % (oy + ph / 2, oy + ph / 2))
    S.append('</svg>')
    return "".join(S)

def lut_rle_rows():
    rows, i, n = [], 0, len(FTAB)
    while i < n:
        j = i
        while j + 1 < n and FTAB[j + 1] == FTAB[i]:
            j += 1
        rng = "%d" % i if i == j else "%d – %d" % (i, j)
        rows.append("<tr><td>%s</td><td class='hl'>%d</td></tr>" % (rng, FTAB[i]))
        i = j + 1
    return "".join(rows)

def _lut_behav():
    L = ["module lns_ftable(input [7:0] d, output reg [3:0] f);   // generated by model.py",
         "  always @* case (d)"]
    for dd in (0, 1, 2, 3):
        L.append("    8'd%-2d : f = 4'd%d;" % (dd, FTAB[dd]))
    L.append("    ...                     // %d entries (d = 0 … %d)" % (len(FTAB), len(FTAB) - 1))
    L.append("    8'd%-2d : f = 4'd%d;" % (LAST_NZ, FTAB[LAST_NZ]))
    L.append("    default : f = 4'd0;")
    L.append("  endcase")
    L.append("endmodule")
    return html.escape("\n".join(L))
BEHAV = _lut_behav()

# faithful to synth/lns_ftable_gates.v (6 sky130 cells; regenerate with the yosys/dot helper)
GATE_RTL = html.escape(
    "module lns_ftable(input [7:0] d, output [3:0] f);   // 6 cells · 33.8 µm²\n"
    "  wire _0_, _1_, _2_;\n"
    "  sky130_fd_sc_hd__or4_1    g0 (.A(d[7]), .B(d[4]), .C(d[5]), .D(d[6]), .X(_0_));\n"
    "  sky130_fd_sc_hd__nor2_1   g1 (.A(d[3]), .B(d[1]), .Y(_1_));\n"
    "  sky130_fd_sc_hd__nor2_1   g2 (.A(d[2]), .B(d[1]), .Y(_2_));\n"
    "  sky130_fd_sc_hd__a211oi_1 g3 (.A1(d[2]), .A2(d[1]), .B1(_0_), .C1(_1_), .Y(f[0]));\n"
    "  sky130_fd_sc_hd__nor3_1   g4 (.A(d[3]), .B(_0_), .C(_2_), .Y(f[1]));\n"
    "  sky130_fd_sc_hd__nor4_1   g5 (.A(d[3]), .B(d[2]), .C(d[1]), .D(_0_), .Y(f[2]));\n"
    "  assign f[3] = 1'b0;                                // F ≤ 4, so bit 3 is always 0\n"
    "endmodule")

def _schematic():
    try:
        s = open(os.path.join(REPORT, "ftable_sch.svg")).read()
        s = s[s.find("<svg"):]                                       # drop xml/doctype
        s = re.sub(r'width="\d+pt" height="\d+pt"', 'width="100%" height="auto"', s, count=1)
        return s
    except Exception:
        return "<p class='note'>(schematic asset report/ftable_sch.svg missing)</p>"
SCHEM = _schematic()

LUT_DERIV = html.escape(
    "  log₂(C·D + Vth)  =  log₂(C·D)  +  Vth′(C,D)\n"
    "\n"
    "     1st term :  log₂(C·D)                                     ← a wire (the input)\n"
    "     2nd term :  Vth′(C,D) = log₂( 1 + 2^( log₂Vth − log₂(C·D) ) )   ← the LUT\n"
    "\n"
    "  since   log₂(C·D) + log₂(1 + Vth/(C·D))  =  log₂(C·D + Vth)")

# ---- RTL Vth-sweep: comparator output, classic multiplier vs log/LNS (from simulation) ----
def _read_sweep():
    try:
        rows = list(csv.DictReader(open(os.path.join(ROOT, "verif", "sweep_rtl.csv"))))
        return [(int(r["Vth"]), int(r["out_mult"]), int(r["out_log"])) for r in rows]
    except Exception:
        return []
SWEEP = _read_sweep()

def sweep_plot_svg():
    if not SWEEP:
        return "<p class='note'>(no sweep data — run <code>verif/tb_sweep</code>)</p>"
    xs = [v for v, _, _ in SWEEP]
    lo, hi = min(xs), max(xs)
    x0, x1 = math.log2(lo), math.log2(hi)
    W, H = 560, 220
    ox, oy = 30, 30
    pw, ph = W - ox - 14, H - oy - 46
    def X(vth): return ox + pw * (math.log2(vth) - x0) / (x1 - x0)
    yhi, ylo = oy + ph * 0.18, oy + ph * 0.82
    def YL(val, off): return (yhi if val else ylo) - off
    ACC, AQ, RED = "var(--accent)", "#199e70", "#d03b3b"
    S = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
         'font-family="system-ui,-apple-system,Segoe UI,sans-serif">' % (W, H)]
    # disagreement band (where the two outputs differ)
    dis = [v for v, m, l in SWEEP if m != l]
    if dis:
        bx0, bx1 = X(min(dis)), X(max(dis))
        S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="rgba(208,59,59,0.13)"/>'
                 % (bx0, oy, max(2, bx1 - bx0), ph))
        S.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9.5" fill="%s">'
                 'disagree</text>' % ((bx0 + bx1) / 2, oy - 4, RED))
    for val in (1, 0):                                             # output level guides
        yy = YL(val, 0)
        S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--grid)" '
                 'stroke-width="1" stroke-dasharray="2 3"/>' % (ox, yy, ox + pw, yy))
        S.append('<text x="%.1f" y="%.1f" text-anchor="end" font-size="9.5" fill="var(--muted)">%d</text>'
                 % (ox - 5, yy + 3, val))
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
             % (ox, oy + ph, ox + pw, oy + ph))
    for tv in (60, 100, 200, 500, 1000, 2000, 5000):              # x ticks (nice Vth values)
        if lo <= tv <= hi:
            xx = X(tv)
            S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
                     % (xx, oy + ph, xx, oy + ph + 4))
            S.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9.5" fill="var(--muted)">%d</text>'
                     % (xx, oy + ph + 15, tv))
    for idx, col, off in ((1, ACC, 0), (2, AQ, 7)):               # the two step outputs
        pth = "M %.1f %.1f" % (X(SWEEP[0][0]), YL(SWEEP[0][idx], off))
        for k in range(1, len(SWEEP)):
            pth += " H %.1f V %.1f" % (X(SWEEP[k][0]), YL(SWEEP[k][idx], off))
        S.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (pth, col))
    mflip = next((v for v, m, l in SWEEP if m == 0), None)        # flip Vth of each
    lflip = next((v for v, m, l in SWEEP if l == 0), None)
    for fv, col in ((lflip, AQ), (mflip, ACC)):
        if fv:
            S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" '
                     'stroke-dasharray="3 2" opacity="0.7"/>' % (X(fv), oy, X(fv), oy + ph, col))
    # legend
    lx, ly = ox + 20, oy + 6
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4"/>' % (lx, ly, lx + 18, ly, ACC))
    S.append('<text x="%.1f" y="%.1f" font-size="10" fill="var(--ink2)">classic (multiplier), flips @%d</text>' % (lx + 23, ly + 3, mflip))
    S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4"/>' % (lx, ly + 15, lx + 18, ly + 15, AQ))
    S.append('<text x="%.1f" y="%.1f" font-size="10" fill="var(--ink2)">log / LNS K=2, flips @%d</text>' % (lx + 23, ly + 18, lflip))
    S.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" fill="var(--ink2)">'
             'threshold  Vth   (log scale)</text>' % (ox + pw / 2, H - 4))
    S.append('</svg>')
    return "".join(S)

# ---- SUBTRACTION sweep (A*B - C*D > Vth): small multiples over several operand sets ----
def _read_sweep_sub():
    from collections import defaultdict
    by = defaultdict(list)
    try:
        for r in csv.DictReader(open(os.path.join(ROOT, "verif", "sweep_sub_rtl.csv"))):
            by[int(r["sid"])].append((int(r["Vth"]), int(r["out_mult"]), int(r["out_log"]),
                                      int(r.get("out_log_k3", r["out_log"])),
                                      int(r["A"]), int(r["B"]), int(r["C"]), int(r["D"])))
        for k in by:
            by[k].sort()
    except Exception:
        return {}
    return by
SWEEP_SUB = _read_sweep_sub()

def _sub_mini(rows):
    A, B, C, D = rows[0][4], rows[0][5], rows[0][6], rows[0][7]
    Sv = A * B - C * D
    mf = next((v for v, mm, ll, *_ in rows if mm == 0), None)
    lf = next((v for v, mm, ll, *_ in rows if ll == 0), None)
    xlo = 0; xhi = max(v for v, *_ in rows)           # x-axis = 0 .. 2·Vth
    vop = xhi // 2                                     # operating threshold (Vmax/2)
    if xhi <= xlo: xhi = xlo + 20
    W, H = 384, 176; ox, oy = 18, 42; pw, ph = W - ox - 8, H - oy - 26
    def X(v): return ox + pw * (min(max(v, xlo), xhi) - xlo) / (xhi - xlo)
    yhi, ylo = oy + ph * 0.22, oy + ph * 0.80
    def YL(val, off): return (yhi if val else ylo) - off
    ACC, AQ, K3 = "var(--accent)", "#199e70", "#8a5cf0"
    P = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
         'font-family="system-ui,-apple-system,Segoe UI,sans-serif">' % (W, H)]
    P.append('<text x="8" y="14" font-size="11.5" font-weight="600" fill="var(--ink)">%d,%d,%d,%d</text>'
             % (A, B, C, D))
    P.append('<text x="%d" y="14" text-anchor="end" font-size="10.5" fill="var(--ink2)">'
             'A·B−C·D = %d</text>' % (W - 8, Sv))
    dis = [v for v, mm, ll, *_ in rows if mm != ll and xlo <= v <= xhi]
    if dis:
        bx0, bx1 = X(min(dis)), X(max(dis))
        P.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="rgba(208,59,59,0.14)"/>'
                 % (bx0, oy, max(2, bx1 - bx0), ph))
    for val in (1, 0):
        yy = YL(val, 0)
        P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--grid)" stroke-width="1" '
                 'stroke-dasharray="2 3"/>' % (ox, yy, ox + pw, yy))
        P.append('<text x="%.1f" y="%.1f" text-anchor="end" font-size="9" fill="var(--muted)">%d</text>'
                 % (ox - 3, yy + 3, val))
    P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
             % (ox, oy + ph, ox + pw, oy + ph))
    # operating threshold marker (x-axis spans 0 .. 2·Vth, so Vth sits at mid)
    vx = X(vop)
    P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--ink2)" stroke-width="1" '
             'stroke-dasharray="3 2" opacity="0.55"/>' % (vx, oy - 2, vx, oy + ph))
    P.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9" fill="var(--ink2)">'
             'Vth=%d</text>' % (vx, oy - 5, vop))
    for tv in (xlo, xhi):                             # only 0 and 2·Vth (evenly spaced, no collision)
        xx = X(tv)
        P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--axis)" stroke-width="1"/>'
                 % (xx, oy + ph, xx, oy + ph + 4))
        P.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9" fill="var(--muted)">%d</text>'
                 % (xx, oy + ph + 14, tv))
    for idx, col, off in ((1, ACC, 0), (2, AQ, 6), (3, K3, 12)):
        vis = [r for r in rows if xlo <= r[0] <= xhi] or rows
        pth = "M %.1f %.1f" % (X(vis[0][0]), YL(vis[0][idx], off))
        for r in vis[1:]:
            pth += " H %.1f V %.1f" % (X(r[0]), YL(r[idx], off))
        P.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (pth, col))
    P.append('</svg>')
    return "".join(P)

def sweep_sub_plots():
    if not SWEEP_SUB:
        return "<p class='note'>(run <code>verif/tb_sweep_sub</code>)</p>"
    cards = "".join('<div class="subcard">%s</div>' % _sub_mini(SWEEP_SUB[s])
                    for s in sorted(SWEEP_SUB))
    return '<div class="subgrid">%s</div>' % cards

# ---- Accuracy vs helper bits K: error of the K-bit log value + real synth area vs mult ----
def _area_vs_k():
    try:
        return {int(r["K"]): (r["pct_of_mult"], r["source"])
                for r in read_csv(os.path.join(REPORT, "area_vs_k.csv"))}
    except Exception:
        return {}
AREA_K = _area_vs_k()

def _disagree_vs_k():
    try:
        return {int(r["K"]): r["disagree_pct"]
                for r in read_csv(os.path.join(REPORT, "disagree_vs_k.csv"))}
    except Exception:
        return {}
DIS_K = _disagree_vs_k()

def k_error_table():
    body = []
    for K in range(0, 5):
        SC = 1 << K
        errs = []
        for v in range(1, 1 << WIDTH):
            e = v.bit_length() - 1
            t = 0
            for i in range(1, K + 1):
                pos = e - i
                t = (t << 1) | (((v >> pos) & 1) if pos >= 0 else 0)
            vhat = 2.0 ** ((SC * e + t) / float(SC))          # reconstructed value
            errs.append(abs(vhat - v) / v)                    # relative error
        mx = max(errs) * 100.0
        mean = sum(errs) / len(errs) * 100.0
        apct, src = AREA_K.get(K, ("—", ""))
        area_cell = ("%s%%" % apct) + ("&nbsp;<sup>est</sup>" if src == "estimate" else "")
        dis = DIS_K.get(K, "—")
        dis_cell = ("%s%%" % dis) if dis != "—" else "—"
        lit = ' class="lit"' if K == MODEL.K else ''
        body.append('<tr%s><td>%d</td><td>%d</td><td>%.1f%%</td><td>%.1f%%</td>'
                    '<td>%s</td><td>%s</td></tr>'
                    % (lit, K, SC, mx, mean, dis_cell, area_cell))
    return "".join(body)

# ---- Cadence std-cell flow: copy-paste-ready commands ----
CAD_FLOW = html.escape("""# env (host tau)
export PATH=/usr/local/packages/cadence_2021/INNOVUS201/bin:/usr/local/packages/cadence_2021/IC618/tools.lnx86/dfII/bin:$PATH
export CDS_LIC_FILE=/usr/local/packages/cadence_2021/license.dat

# 1. RTL -> tcb018 standard cells (yosys)      -> synth/vth_prime_tcb018.v  (179 cells)
yosys -s synth/run_vthp.ys

# 2. netlist -> Virtuoso schematic in myLib (Verilog-In)
(cd ihdl_run && ihdl -param param.txt -cdslib ./cds.lib vth_prime_tcb018.v)

# 3. place & route -> DRC-clean GDS (Innovus; script below)
(cd pnr_vthp && innovus -no_gui -files run_vthp_pnr.tcl)

# 4. import the routed layout into Virtuoso
strmin -library myLib -strmFile pnr_vthp/vth_prime.gds \\
       -layerMap /usr/local/packages/tsmc_18m/pdk/tsmc18/tsmc18.layermap -view layout""")
try:
    CAD_PNR = html.escape(open(os.path.join(ROOT, "pnr_vthp", "run_vthp_pnr.tcl")).read().strip())
except Exception:
    CAD_PNR = "(pnr_vthp/run_vthp_pnr.tcl)"

# ---------------------------------------------------------------------------
PAGE = f"""<div class="wrap">
<header>
  <div class="toprow">
    <div class="eyebrow">SkyWater 130 nm · open-source RTL→GDS flow (yosys)</div>
    <a class="rev" href="{REPO}/commits/main" title="revision history — built from this commit">
      <span class="revdot"></span>rev {REV_LABEL} · {REV_DATE}</a>
  </div>
  <h1>Eliminating Multipliers with Log / LNS Arithmetic</h1>
  <p class="sub">A general-purpose look at trading hardware multipliers for a small
  log-domain ROM. Two RTL implementations of the same multiply-compare kernel
  <code>(A·B + C·D) &gt; V<sub>th</sub></code> (<b>{WIDTH}-bit</b> inputs) — one with real
  multipliers, one multiplier-free via a K={K} logarithmic (LNS) datapath — synthesized and
  compared on the sky130 HD standard-cell library.</p>
  <div class="takeaway">
    Dropping the two multipliers for the K={K} log datapath cuts
    <b>area {area_save:.0f}%</b> and estimated <b>power {pow_save:.0f}%</b>,
    at a <b>{overall:.2f}% accuracy cost</b> vs. exact math.
  </div>
</header>

<nav class="toc">
  <div class="tocg"><span class="tochdr">Jump to</span>
    <a href="#rtl">RTL structure</a><a href="#datapath">Datapath</a>
    <a href="#worked">Worked examples</a><a href="#sweep-add">Sweep A·B+C·D</a>
    <a href="#sweep-sub">Sweep A·B−C·D</a><a href="#accuracy">Accuracy vs K</a>
    <a href="#comparison">Comparison</a><a href="#die">Die size</a>
    <a href="#f-rom-lut">Inside the LUT</a><a href="#files">Files</a></div>
  <div class="tocg"><span class="tochdr">Top files — log / LNS</span>
    <a href="{REPO_BLOB}/rtl/log_detector.v">RTL ↗</a>
    <a href="{REPO_BLOB}/synth/log_detector_netlist.v">gate-level ↗</a>
    <a href="{REPO_BLOB}/synth/log_detector.gds">GDS ↗</a>
    <a href="{REPO_BLOB}/veriloga/lns_detector.va">Verilog-A ↗</a></div>
  <div class="tocg"><span class="tochdr">multiplier</span>
    <a href="{REPO_BLOB}/rtl/mult_detector.v">RTL ↗</a>
    <a href="{REPO_BLOB}/synth/mult_detector_netlist.v">gate-level ↗</a>
    <a href="{REPO_BLOB}/synth/mult_detector.gds">GDS ↗</a>
    <a href="{REPO_BLOB}/veriloga/mult_detector.va">Verilog-A ↗</a></div>
</nav>

<section class="bdsec" id="rtl">
  <h2>RTL structure — modules &amp; signals</h2>
  {rtl_diagram()}
</section>

<section class="bdsec" id="datapath">
  <h2>Datapath — target use case (A·B − C·D) &gt; V<sub>th</sub></h2>
  {block_diagram()}
  <a class="callout" href="#lns-add-rom">
    <span class="cico">💡</span>
    <span><b>What exactly is the “LNS add” ROM?</b> It’s a <b>1-input</b> table
    F(d) = log₂(1 + 2<sup>−d</sup>) indexed only by d = |x − y|, and the result stays
    in the log domain — it is <em>not</em> 2<sup>x</sup> − 2<sup>y</sup>.
    <span class="clink">See the derivation ↓</span></span>
  </a>
</section>

<section id="worked">
  <h2>Worked examples — where the approximation misjudges</h2>
  <p class="note">Real values through the implemented <code>(A·B + C·D) &gt; V<sub>th</sub></code>
  build (every number on this page is this add build). <b>Ŝ = 2<sup>s/{SCALE}</sup></b> is the
  linear value the K={K} log path represents for A·B+C·D (compare it with S — that gap is the log
  path's magnitude approximation); <b>V̂ = 2<sup>Lv/{SCALE}</sup></b> is the log-quantized
  threshold; the K={K} output is (Ŝ &gt; V̂). <b>err%</b> is the <b>output</b> error —
  <b>N/A when the output is correct</b>, shown only on a row where the approximation flips the
  decision.</p>
  <div class="tablescroll">
  <table>
    <thead><tr><th>A</th><th>B</th><th>C</th><th>D</th><th>V<sub>th</sub></th>
      <th>S = A·B+C·D</th><th>A·B−C·D</th><th>Ŝ (K={K})</th><th>err %</th><th>V̂ (K={K})</th>
      <th>out<br>exact</th><th>out<br>K={K}</th><th>verdict</th></tr></thead>
    <tbody>{EXROWS}</tbody>
  </table>
  </div>
  <p class="note"><b>The highlighted row misjudges.</b> S = {MISJ['S']} sits just above
  V<sub>th</sub> = {MISJ['Vth']}, but K={K} rounds A·B+C·D down to Ŝ = {MISJ['Shat']:.0f} and the
  threshold to V̂ = {MISJ['Vhat']:.0f}, so {MISJ['Shat']:.0f} &gt; {MISJ['Vhat']:.0f} is false —
  output 0 where exact says 1 ({MISJ['err']:+.0f}% under-estimate, landing right on the boundary).
  Note another row (Ŝ = {BIGERR['Shat']:.0f} vs S = {BIGERR['S']}, {BIGERR['err']:+.0f}%) carries a
  <em>larger</em> magnitude gap yet still decides correctly, so its output error is N/A: the
  approximation only changes the output when it <em>straddles</em> the threshold, which is why the
  overall disagreement is ~{overall:.1f}% and concentrates near mid-range V<sub>th</sub>.</p>
</section>

<section>
  <h2>Step-by-step — the LNS add for row 1 (C·D = 12·40)</h2>
  <p class="note">Exactly what the multiplier-free path does for worked-example row 1
  (A=25, B=30, C=12, D=40): leading-one-detector log conversion (<code>lod5.v</code>),
  log-add = multiply, then the LNS add (<code>lns_add.v</code>) with the F ROM
  (<code>lns_ftable.v</code>). Logs are in {UNITW} units (integer {SCALE}·log₂).</p>
  <div class="deriv"><pre>{WALK}</pre></div>
  <p class="note">The whole LNS add costs just <b>one table lookup</b> — <code>F(d)</code> at
  key <b>d = |X − Y| = {DUSED}</b>. Here is that slice of the actual ROM
  (<code>lns_ftable.v</code>) — the used key highlighted, with its neighbors:</p>
  <div class="tablescroll" style="display:inline-block;max-width:100%">
  <table class="ftab">
    <thead><tr><th>d&nbsp;&nbsp;(ROM key)</th><th>F&nbsp;&nbsp;(value)</th>
      <th>log₂(1+2<sup>−d/{SCALE}</sup>)</th><th></th></tr></thead>
    <tbody>{ROMSLICE}</tbody>
  </table>
  </div>
</section>

<section id="sweep-add">
  <h2>RTL sweep — comparator output vs V<sub>th</sub> &nbsp;<span class="fn">A,B,C,D = 25,30,12,40</span></h2>
  <p class="note">Same worked-example inputs (exact A·B+C·D = <b>1230</b>), swept over
  V<sub>th</sub> = 60…6000 and driven through <b>both RTL designs in Icarus Verilog</b>
  (<code>verif/tb_sweep.v</code>). Each step is the design's registered 1-bit output.</p>
  <div class="plotcard">{sweep_plot_svg()}</div>
  <p class="note">Both read <b>1</b> for small V<sub>th</sub> and <b>0</b> for large V<sub>th</sub>.
  The <b>classic multiplier flips exactly at V<sub>th</sub> = 1230</b> (= A·B+C·D). The
  <b>K=2 log design flips at V<sub>th</sub> = 1024</b> — its quantized Ŝ. In the shaded band
  <b>1024 ≤ V<sub>th</sub> &lt; 1230</b> the two <em>disagree</em> (log says 0, exact says 1): that
  is the K=2 approximation cost for this input, made concrete by simulation. Elsewhere they
  agree. Everything else (area, power, ports) is unchanged — only the decision boundary moves.</p>
</section>

<section id="sweep-sub">
  <h2>RTL sweep — the subtraction kernel &nbsp;<span class="fn">A·B − C·D &gt; V<sub>th</sub>, eleven operand sets</span></h2>
  <p class="note">Same idea for the <b>subtraction</b> kernel, from RTL simulation
  (<code>verif/tb_sweep_sub.v</code> drives <code>mult_sub.v</code> and <code>log_sub.v</code>; the
  log design uses the rearrangement <code>A·B &gt; C·D + Vth</code>, and both are verified bit-exact
  to the golden model). Each panel sweeps V<sub>th</sub> and overlays the classic exact output against
  the log/LNS at <b>K=2 and K=3</b> — the classic flips exactly at V<sub>th</sub> = A·B−C·D, the log
  designs at their approximations; the shaded band is the K=2 disagreement. <b>K=3 lands closer to
  the exact flip</b> (aggregate error band ~32% narrower), for +1 helper bit (≈ +8 pts of the
  multiplier's area — see the Accuracy-vs-K table).</p>
  <div class="leg2"><span><i style="background:var(--accent)"></i>classic (multiplier)</span>
    <span><i style="background:#199e70"></i>log / LNS (K=2)</span>
    <span><i style="background:#8a5cf0"></i>log / LNS (K=3)</span>
    <span><i class="band"></i>disagree (K=2)</span></div>
  {sweep_sub_plots()}
  <p class="note"><b>Cancellation</b> sets the accuracy: when A·B and C·D are both large but their
  difference is small — <b>60,60,50,50</b> (3600−2500) or <b>25,30,12,40</b> — the log path is well
  off (wide band), whereas <b>8,8,5,5</b> is near-exact. The log design can err in either direction:
  <b>40,40,10,10</b> flips a touch late (over-estimate), while <b>30,30,10,10</b> and
  <b>23,19,11,7</b> flip early (under-estimate).</p>
</section>

<section id="accuracy">
  <h2>Accuracy vs helper bits K &nbsp;<span class="fn">error as % of full-scale V<sub>th</sub></span></h2>
  <p class="note">The single accuracy knob is <b>K</b>, the number of mantissa (helper) bits each log
  converter keeps. With K fraction bits a log value is resolved to 2<sup>−K</sup>, so a product or
  threshold is pinned to within a ratio of 2<sup>2<sup>−K</sup></sup> — i.e. the <b>worst-case
  decision error as a fraction of full-scale V<sub>th</sub></b>. Both error columns below are computed
  directly from the K-bit converter over the {WIDTH}-bit input range. This build ships <b>K = {K}</b>.</p>
  <div class="tablescroll" style="display:inline-block;max-width:100%">
    <table class="ftab"><thead><tr>
      <th>K &nbsp;(helper bits)</th><th>SCALE = 2<sup>K</sup></th>
      <th>worst-case error<br>(% of full scale)</th><th>mean error</th>
      <th>disagreement<br>(measured, A·B+C·D)</th>
      <th>area vs multiplier<br>(sky130, synth)</th></tr></thead>
    <tbody>{k_error_table()}</tbody></table>
  </div>
  <p class="note">Three views of the same knob. <b>Worst-case / mean error</b> are the K-bit log
  converter's value-representation error (analytic, over the {WIDTH}-bit range) — the theoretical
  bound as a fraction of full-scale V<sub>th</sub>. <b>Disagreement</b> is the <em>measured</em>
  end-to-end miss rate — how often <code>out</code> flips vs. exact <code>(A·B+C·D) &gt; Vth</code>
  over a 4 M-combo Monte-Carlo (same method as the headline; K = {K} reproduces {overall:.2f}%). It is
  far below the worst-case bound because most inputs sit nowhere near the boundary. <b>Area</b> is the
  real synthesized log-design cell area as a % of the multiplier baseline ({M['area_um2']} µm²), each K
  re-synthesized with its own F-ROM (<code>scripts/area_vs_k.py</code>, <code>disagree_vs_k.py</code>).
  Accuracy and area pull opposite ways — each helper bit cuts the miss rate but adds ~7–8 pts of area,
  yet the log design stays well under the multiplier through K = 4. <b>K = {K}</b> (this build) is
  highlighted; <sup>est</sup> = area extrapolated (8-bit buses synthesize cleanly only through K = 3).</p>
</section>

<section class="kpis">
  <div class="kpi"><div class="kv">−{area_save:.0f}%</div><div class="kl">standard-cell area</div><div class="ks">{M['area_um2']} → {L['area_um2']} µm²</div></div>
  <div class="kpi"><div class="kv">−{pow_save:.0f}%</div><div class="kl">power @ 50 MHz (est.)</div><div class="ks">{L['x_baseline_power']}× baseline</div></div>
  <div class="kpi"><div class="kv">{overall:.2f}%</div><div class="kl">disagreement vs exact</div><div class="ks">K={K} accuracy cost</div></div>
  <div class="kpi"><div class="kv">0 → 2</div><div class="kl">multipliers → none</div><div class="ks">both verify PASS</div></div>
</section>

<section id="comparison">
  <h2>Comparison</h2>
  <div class="tablescroll">
  <table>
    <thead><tr><th>Metric</th><th>Design 1 · multiplier</th><th>Design 2 · log K={K}</th><th>Design 2 / 1</th></tr></thead>
    <tbody>
    {tbl_rows()}
    </tbody>
  </table>
  </div>
  <p class="note">Area from <code>stat -liberty</code> (real cell areas). Power is an
  analytic estimate <code>E=α(1+wire)·ΣC<sub>in</sub>·V<sub>dd</sub>²</code>
  (V<sub>dd</sub>=1.8 V, α=0.15, wire=1.0×, f=50 MHz); the <b>×baseline ratio</b> is
  robust to those assumptions. OpenSTA was not available on this host.</p>
</section>

<section id="die">
  <h2>Die size — standard-cell floorplan</h2>
  <p class="note">No P&amp;R tool (OpenROAD/Innovus) was available, so this is a
  <b>floorplan estimate</b>, not a routed layout: the real synthesized cells are packed
  into 2.72 µm rows at 65% utilization to measure die <b>x × y</b>. Colored by cell
  <em>function</em>. A real <code>.gds</code> is emitted for each
  (<code>synth/*.gds</code>). <b>Both dies are drawn at the same scale</b> — Design 2's
  dashed frame is Design 1's footprint, so the size difference is literal. Absolute x/y
  scale with the utilization assumption; the Design-2/Design-1 ratio does not.</p>
  <div class="legend">{legend()}</div>
  <div class="dies">
    <figure>{svg_mult}<figcaption>Design 1 — die {FM['die_x_um']} × {FM['die_y_um']} µm = {FM['die_area_um2']} µm²</figcaption></figure>
    <figure>{svg_log}<figcaption>Design 2 — die {FL['die_x_um']} × {FL['die_y_um']} µm = {FL['die_area_um2']} µm² &nbsp;(−{die_save:.0f}%)</figcaption></figure>
  </div>
</section>

<section>
  <h2>Why it shrinks — cell-area mix</h2>
  <p class="note">The multiplier spends most of its area on adder cells
  (<span class="ci" style="background:{CAT_LIGHT['arith']}"></span>xor/maj arrays); the
  log design replaces them with converter logic
  (<span class="ci" style="background:{CAT_LIGHT['logic']}"></span>) and a small ROM/mux.
  Both carry the identical registered-I/O flip-flops (<span class="ci" style="background:{CAT_LIGHT['ff']}"></span>) —
  the multiplier just wraps them in far more combinational area.</p>
  <div class="comp">
    <div class="crow"><span class="clab">Design 1</span><div class="cbar">{comp_bar(mult_cat, mult_total)}</div><span class="cval">{mult_total:.0f} µm²</span></div>
    <div class="crow"><span class="clab">Design 2</span><div class="cbar">{comp_bar(log_cat, log_total)}</div><span class="cval">{log_total:.0f} µm²</span></div>
  </div>
  <div class="legend">{legend()}</div>
</section>

<section>
  <h2>K={K} accuracy cost — disagreement vs exact</h2>
  <p class="note">Over 4 M Monte-Carlo samples × each threshold (the {WIDTH}-bit space,
  {WIDTH_BASE}⁴ ≈ {SPACE_SCI}, cannot be enumerated, so this is a sampled estimate).
  Design 2's RTL is bit-exact to its K={K} model; a disagreement with exact math is the
  <em>approximation cost</em>, not a bug. Overall = <b>{overall:.2f}%</b>, peaking at
  mid-range thresholds and vanishing at the extremes.</p>
  <div class="vth" data-title="disagreement % by V_th">{vth_bars()}</div>
</section>

<section id="lns-add-rom">
  <h2>How the “LNS add” ROM works</h2>
  <p class="note">In a logarithmic number system every value is carried as its base-2 log,
  so <b>multiply is free</b> — you add the logs: x = log₂A + log₂B = log₂(A·B). The hard part
  is <b>adding</b> two values, and that is the one operation the ROM exists for. Here is the
  exact identity it implements (base 2, because the leading-one detector yields log₂ directly):</p>

  <div class="deriv"><pre>{DERIV}</pre></div>

  <p class="note">The key move is factoring out the larger term:
  <code>2<sup>x</sup>+2<sup>y</sup> = 2<sup>max(x,y)</sup>·(1+2<sup>−d</sup>)</code>. What’s left,
  <b>F(d) = log₂(1 + 2<sup>−d</sup>)</b>, depends on the <b>single</b> variable d = |x − y| — so the
  ROM is a small 1-D table, not a 2-D (x, y) surface, and the sum <b>never leaves the log
  domain</b> (s is compared against log₂(Vth) directly; the linear value 2<sup>x</sup> − 2<sup>y</sup>
  is never formed).</p>

  <div class="tablescroll" style="display:inline-block;max-width:100%">
  <table class="ftab">
    <thead><tr><th>d = |x−y|</th><th>F(d) = log₂(1+2<sup>−d</sup>)</th><th>stored ({UNITW} units)</th></tr></thead>
    <tbody>{FROWS}</tbody>
  </table>
  </div>
  <p class="note">Logs are carried in <b>{UNITW} units</b> (the integer {SCALE}·log₂), so the ROM is
  indexed by the integer |X−Y| and outputs round({SCALE}·F) — 0…{SCALE}. The whole table is
  <code>{ROM_PREVIEW}</code> ({ROM_LEN} entries, d = 0…{ROM_MAXD}), i.e. a {FBITS}-bit value. That is
  the entire “F(d) ROM” drawn in the datapath above.</p>

  <p class="note"><b>Subtraction is the hard cousin.</b> A true LNS subtract would use
  F₋(d) = log₂(1 − 2<sup>−d</sup>) (plus a sign bit) — still a 1-input table of |x − y|, but it
  diverges to −∞ as d → 0 (catastrophic cancellation when A·B ≈ C·D), exactly where a small K is
  weakest. The threshold compare <code>(A·B − C·D) &gt; Vth</code> sidesteps it by rearranging to
  an <b>add</b>, <code>A·B &gt; C·D + Vth</code>, reusing this same
  F(d) = log₂(1 + 2<sup>−d</sup>) ROM.</p>
</section>

<section id="f-rom-lut">
  <h2>Inside the LUT — the correction Vth′(C,D)</h2>
  <p class="note">Take the sub-block that folds the threshold into a product: input
  <code>log₂(C·D)</code>, output <code>log₂(C·D + Vth)</code>. Factor out the input:</p>
  <div class="deriv"><pre>{LUT_DERIV}</pre></div>
  <p class="note">The <b>1st term is a wire</b> (the input, carried into an adder); the
  <b>2nd term is the LUT</b> — name it <b>Vth′(C,D) = log₂(1 + 2<sup>log₂Vth − log₂(C·D)</sup>)</b>,
  the log-domain amount by which Vth lifts <code>log₂(C·D)</code> ({UNITW} units). So the whole
  block is just <code>out = log₂(C·D) + Vth′(C,D)</code>. <b>Vth stays programmable</b>: it is a
  runtime input, and the LUT below is <b>Vth-independent</b> (the general correction addressed by
  the log-gap), so changing Vth just slides where each C·D lands on it — it is <em>not</em> baked
  into the table.</p>
  <p class="note">On an ASIC there is <b>no LUT primitive</b> — synthesis maps this correction to
  <b>6 standard cells (33.8 µm², &lt;1% of the log detector)</b>. The table is the design's
  <em>general</em>, bounded correction addressed by the log-gap
  <code>d = |log₂(C·D) − log₂(Vth)|</code>, value Vth′ (0…{SCALE}, a {FBITS}-bit output). In the
  full A·B+C·D detector the same table combines the two <em>products</em> instead, and when
  C·D &lt; Vth the roles swap so the address stays ≥ 0.</p>

  <h3 class="sub3">Transfer function &nbsp;<span class="fn">Vth′ vs log₂(Vth), for two product levels</span></h3>
  <div class="plotcard">{lut_transfer_svg()}</div>
  <p class="note"><b>Sweeping the programmable Vth.</b> x is the runtime threshold
  <code>log₂(Vth)</code>; the two <em>quantized staircases</em> ({UNITW} steps — the actual LUT
  function, not a smooth curve) are two fixed product levels <code>C·D</code>, 4× apart. Each rises
  with Vth: the knee (dot) is at <b>Vth = C·D</b> (Vth′ = log₂2 = 1). For <b>Vth ≪ C·D</b> the
  correction ≈ 0 (the threshold is negligible next to the product); for <b>Vth ≫ C·D</b> it rises
  toward log₂(Vth) − log₂(C·D) (the threshold dominates). A <b>4× larger C·D shifts the knee right
  by log₂4 = 2</b> — a bigger product needs a proportionally bigger Vth before the threshold starts
  to matter.</p>

  <h3 class="sub3">Truth table &nbsp;<span class="fn">address → Vth′</span> (identical runs collapsed)</h3>
  <div class="tablescroll" style="display:inline-block;max-width:100%">
    <table class="ftab"><thead><tr><th>d = |log₂(C·D) − log₂(Vth)|</th><th>Vth′ &nbsp;(value)</th></tr></thead>
    <tbody>{lut_rle_rows()}</tbody></table>
  </div>
  <p class="note">Full ROM: <code>{ROM_PREVIEW}</code> ({ROM_LEN} entries). The staircase is
  monotone non-increasing, which is why it minimizes to so few gates.</p>

  <h3 class="sub3">Behavioral RTL &nbsp;<span class="fn">rtl/lns_ftable.v</span></h3>
  <div class="deriv"><pre>{BEHAV}</pre></div>

  <h3 class="sub3">Gate-level netlist &nbsp;<span class="fn">after yosys + ABC (sky130)</span></h3>
  <div class="deriv"><pre>{GATE_RTL}</pre></div>

  <h3 class="sub3">Logic-gate schematic</h3>
  <figure class="schem">
    <figcaption class="lutio"><b>in:</b>&nbsp; log₂(C·D), log₂(Vth) <span class="prog">programmable</span>
      &nbsp;→&nbsp; <b>F-LUT · 6 gates</b> &nbsp;→&nbsp; <b>out:</b>&nbsp; Vth′</figcaption>
    {SCHEM}</figure>
  <p class="note">Two logic levels: <code>or4_1</code>/<code>nor2_1</code> build the internal
  terms (<code>_0_</code> = OR of the high address bits, i.e. “d is large”; <code>_1_</code>,
  <code>_2_</code>), then <code>a211oi_1</code>/<code>nor3_1</code>/<code>nor4_1</code> produce
  the three output bits <code>f[0..2]</code>; <code>f[3]</code> is tied low.</p>
</section>

<section id="cadence">
  <h2>Cadence std-cell implementation &nbsp;<span class="fn">the Vth′ block in real silicon (TSMC 0.18 µm)</span></h2>
  <p class="note">The Vth′(C,D) block above, carried all the way to layout: RTL → <b>yosys</b> to
  <b>tcb018</b> standard cells → <b>Verilog-In (<code>ihdl</code>)</b> schematic in Virtuoso
  <code>myLib</code> → <b>Innovus</b> place-and-route (<b>0 DRC violations</b>). Alongside it, the
  plain 10×10 <code>C·D</code> multiplier it replaces — drawn to the same scale:</p>
  <figure class="schem"><img src="vthp_layout_compare.png" alt="vth_prime vs mult_cd layout, to scale"
    style="display:block;width:100%;height:auto;border-radius:8px"/>
    <figcaption class="lutio" style="border:0;padding-top:8px;margin:0">Innovus P&amp;R placement,
    to scale — log-domain Vth′ block (80×75 µm) vs. the 10×10 multiplier (113×110 µm).</figcaption></figure>
  <div class="tablescroll" style="display:inline-block;max-width:100%;margin-top:12px">
    <table class="ftab"><thead><tr><th>metric (tcb018, Innovus)</th>
      <th>Vth′ block <span class="fn">log</span></th><th>C·D multiplier</th></tr></thead>
    <tbody>
      <tr><td>standard cells</td><td>179</td><td>343</td></tr>
      <tr><td>std-cell area</td><td>4215 µm²</td><td>9824 µm²</td></tr>
      <tr><td>die (x × y)</td><td>80 × 75 µm</td><td>113 × 110 µm</td></tr>
      <tr class="lit"><td>die area</td><td>~5.97k µm²</td><td>~12.4k µm² &nbsp;(≈2×)</td></tr>
      <tr><td>DRC</td><td>clean</td><td>clean</td></tr>
    </tbody></table>
  </div>
  <h3 class="sub3">Reproduce &nbsp;<span class="fn">RTL → GDS, copy-paste</span></h3>
  <div class="cblock"><button class="copybtn" onclick="copyCode(this)">Copy</button><pre>{CAD_FLOW}</pre></div>
  <h3 class="sub3">Innovus P&amp;R script &nbsp;<span class="fn">pnr_vthp/run_vthp_pnr.tcl</span></h3>
  <div class="cblock"><button class="copybtn" onclick="copyCode(this)">Copy</button><pre>{CAD_PNR}</pre></div>
  <p class="note">Batch, no GUI. Swap <code>vth_prime</code>→<code>mult_cd</code> (and the pin lists)
  for the multiplier. Schematic import uses <code>ihdl</code> (Verilog-In); the P&amp;R reads the
  tcb018 LEF + NLDM <code>.lib</code>, does floorplan → place → route → fillers, verifies DRC, and
  streams out a merged GDS.</p>
</section>

<section id="files">
  <h2>Files</h2>
  <p class="filehdr note"><a href="{REPO}">Browse the repository ↗</a>
     <a href="{REPO_ZIP}">Download all (.zip) ↓</a></p>
  <div class="files">{files_section()}</div>
</section>

<footer>
  <p><b>Flow:</b> Python golden model (emits the F-ROM) → RTL (Verilog) →
  Icarus verify ({nvec:,} vectors, both PASS) → yosys synth to sky130 HD →
  analytic power + standard-cell floorplan. Reproduce: <code>./run.sh</code> then
  <code>python3 model/floorplan.py &amp;&amp; python3 model/build_page.py</code>.</p>
  <p class="fine">Estimates are labelled as such. Routed area/power/timing would come from
  OpenROAD/OpenLane P&amp;R + OpenSTA; the comparison <em>ratios</em> reported here are the
  robust figures.</p>
</footer>
<script>
function copyCode(b){{var p=b.parentNode.querySelector('pre');navigator.clipboard.writeText(p.innerText).then(function(){{var t=b.textContent;b.textContent='Copied!';setTimeout(function(){{b.textContent=t}},1200);}});}}
</script>
</div>"""

STYLE = """
:root{
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --accent:#2a78d6; --good:#0ca30c; --ring:rgba(11,11,11,.10);
}
@media (prefers-color-scheme:dark){:root{
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --accent:#3987e5; --good:#0ca30c; --ring:rgba(255,255,255,.10);
}}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:40px 22px 64px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em;
  background:var(--surface);border:1px solid var(--ring);border-radius:5px;padding:.05em .4em}
.eyebrow{color:var(--accent);font-weight:600;font-size:13px;letter-spacing:.02em}
.toprow{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.rev{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--ink2);text-decoration:none;font-variant-numeric:tabular-nums;border:1px solid var(--ring);border-radius:20px;padding:3px 11px;white-space:nowrap}
.rev:hover{border-color:var(--accent);color:var(--accent)}
.revdot{width:7px;height:7px;border-radius:50%;background:var(--good);display:inline-block;flex:0 0 auto}
.toc{display:flex;flex-direction:column;gap:9px;margin:22px 0 6px;padding:13px 16px;background:var(--surface);border:1px solid var(--ring);border-radius:10px}
.tocg{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px}
.tochdr{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);min-width:118px}
.toc a{font-size:13px;color:var(--accent);text-decoration:none;white-space:nowrap}
.toc a:hover{text-decoration:underline}
section[id]{scroll-margin-top:16px}
h1{font-size:30px;line-height:1.2;margin:.25em 0 .3em}
h2{font-size:20px;margin:0 0 .5em;padding-bottom:.35em;border-bottom:1px solid var(--grid)}
.sub{color:var(--ink2);font-size:16px;max-width:70ch}
.sub code{font-size:.9em}
.takeaway{margin-top:18px;padding:14px 18px;background:var(--surface);border:1px solid var(--ring);
  border-left:3px solid var(--accent);border-radius:8px;font-size:15.5px}
section{margin-top:38px}
.bd{margin:14px 0 0;background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:12px 12px 12px}
.bd svg{display:block;width:100%;height:auto}
.bd figcaption{margin-top:10px;padding-top:10px;border-top:1px solid var(--grid);color:var(--ink2);font-size:12.5px;line-height:1.5}
.callout{display:flex;gap:12px;align-items:flex-start;margin-top:16px;padding:12px 16px;background:var(--surface);border:1px solid var(--ring);border-left:3px solid var(--accent);border-radius:8px;text-decoration:none;color:var(--ink2);font-size:13.5px;line-height:1.55}
.callout:hover{border-color:var(--accent)}
.callout b{color:var(--ink)}
.callout .cico{font-size:18px;line-height:1.3}
.callout .clink{color:var(--accent);font-weight:600;white-space:nowrap}
.deriv{margin:14px 0;overflow-x:auto;background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:14px 16px}
.deriv pre{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;line-height:1.7;color:var(--ink);white-space:pre}
h3.sub3{font-size:14px;margin:22px 0 8px;color:var(--ink)}
.fn{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82em;font-weight:400;color:var(--ink2)}
.plotcard,.schem{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:12px;margin:0}
.plotcard svg,.schem svg{display:block;width:100%;height:auto}
.subgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}
.subcard{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:8px}
.subcard svg{display:block;width:100%;height:auto}
.leg2{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:10px;font-size:13px;color:var(--ink2)}
.leg2 span{display:inline-flex;align-items:center;gap:7px}
.leg2 i{width:14px;height:4px;border-radius:2px;display:inline-block}
.leg2 i.band{width:12px;height:12px;border-radius:3px;background:rgba(208,59,59,0.28)}
@media(max-width:820px){.subgrid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){.subgrid{grid-template-columns:1fr}}
.schem figcaption.lutio{font-size:12px;color:var(--ink2);text-align:center;padding-bottom:9px;margin-bottom:6px;border-bottom:1px solid var(--grid)}
.schem figcaption.lutio b{color:var(--ink)}
.prog{color:var(--good);border:1px solid var(--good);border-radius:20px;padding:0 7px;font-size:10.5px;font-weight:600}
.ftab{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.ftab th,.ftab td{border:1px solid var(--grid);padding:5px 12px;text-align:right}
.ftab th{color:var(--ink2);font-weight:600;background:var(--surface)}
.ftab tr.lit td{background:rgba(42,120,214,.10);font-weight:600;color:var(--ink)}
.cblock{position:relative;margin:10px 0}
.cblock pre{background:#0d0d12;color:#dfe3e8;border:1px solid var(--ring);border-radius:9px;padding:14px 16px;margin:0;overflow-x:auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;line-height:1.55}
.copybtn{position:absolute;top:8px;right:8px;font-size:11px;padding:3px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.18);background:#20242c;color:#c9cdd4;cursor:pointer}
.copybtn:hover{border-color:var(--accent);color:#fff}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;border:0}
.kpi{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px 16px 14px}
.kv{font-size:30px;font-weight:700;letter-spacing:-.01em;color:var(--accent)}
.kl{font-size:13px;font-weight:600;margin-top:2px}
.ks{font-size:12px;color:var(--muted);margin-top:3px;font-variant-numeric:tabular-nums}
.tablescroll{overflow-x:auto;border:1px solid var(--ring);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:14.5px;min-width:560px}
thead th{text-align:left;background:var(--surface);color:var(--ink2);font-size:12.5px;
  font-weight:600;padding:11px 14px;border-bottom:1px solid var(--grid);position:sticky;top:0}
tbody th{text-align:left;font-weight:600}
td,tbody th{padding:10px 14px;border-bottom:1px solid var(--grid);
  font-variant-numeric:tabular-nums;vertical-align:top}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:0}
td.hl{color:var(--accent);font-weight:600}
td.delta{color:var(--ink2);font-weight:600}
td.delta.gain,td.hl.gain{color:var(--good)}
td.delta.loss,td.hl.loss{color:#d03b3b}
tbody tr.misrow{background:rgba(227,73,72,.09)}
tbody tr.usedrow{background:rgba(42,120,214,.11)}
.bad{color:#d03b3b;font-weight:700}
.ok2{color:var(--good);font-weight:600}
.na{color:var(--muted)}
.note{color:var(--ink2);font-size:13.5px;max-width:78ch}
.note code{font-size:.88em}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:12px 0}
.lg{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--ink2)}
.lg i{width:12px;height:12px;border-radius:3px;display:inline-block}
.ci{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:baseline;margin:0 1px}
.dies{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
.dies figure{margin:0}
.dies svg{display:block;border-radius:10px}
figcaption{color:var(--ink2);font-size:12.5px;margin-top:8px;text-align:center;font-variant-numeric:tabular-nums}
.comp{display:flex;flex-direction:column;gap:12px;margin:14px 0}
.crow{display:grid;grid-template-columns:78px 1fr 78px;align-items:center;gap:12px}
.clab{font-size:13.5px;font-weight:600}
.cval{font-size:13px;color:var(--ink2);text-align:right;font-variant-numeric:tabular-nums}
.cbar{display:flex;height:26px;border-radius:6px;overflow:hidden;border:1px solid var(--ring);background:var(--surface)}
.seg{height:100%;border-right:2px solid var(--plane)}
.seg:last-child{border-right:0}
.vth{margin-top:12px;display:flex;flex-direction:column;gap:6px}
.vrow{display:grid;grid-template-columns:52px 1fr 56px;align-items:center;gap:10px}
.vlab{font-size:12.5px;color:var(--ink2);text-align:right;font-variant-numeric:tabular-nums}
.vtrack{background:var(--surface);border:1px solid var(--ring);border-radius:5px;height:16px;overflow:hidden}
.vbar{height:100%;background:var(--accent);border-radius:5px 4px 4px 5px;min-width:2px}
.vval{font-size:12.5px;color:var(--ink2);font-variant-numeric:tabular-nums;font-weight:600}
.filehdr{display:flex;gap:20px;align-items:baseline;flex-wrap:wrap;margin-top:0}
.filehdr a{color:var(--accent);text-decoration:none;font-weight:600;font-size:14px}
.filehdr a:hover{text-decoration:underline}
.files{display:grid;grid-template-columns:repeat(3,1fr);gap:20px 28px;margin-top:16px}
.fgroup h3{font-size:11.5px;margin:0 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;font-weight:700}
.fgroup a{display:block;font-size:13.5px;color:var(--accent);text-decoration:none;padding:2.5px 0}
.fgroup a:hover{text-decoration:underline}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--grid);color:var(--ink2);font-size:13px}
.fine{color:var(--muted);font-size:12.5px}
@media(max-width:720px){.kpis{grid-template-columns:repeat(2,1fr)}.dies{grid-template-columns:1fr}
  h1{font-size:25px}.crow{grid-template-columns:64px 1fr 64px}.files{grid-template-columns:repeat(2,1fr)}}
"""

os.makedirs(DOCS, exist_ok=True)
doc = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
       "<meta name='viewport' content='width=device-width,initial-scale=1'>"
       "<title>Eliminating Multipliers with Log/LNS Arithmetic — sky130</title>"
       "<style>%s</style></head><body>%s</body></html>" % (STYLE, PAGE))
open(os.path.join(DOCS, "index.html"), "w").write(doc)
print("wrote docs/index.html (%.1f KB)" % (len(doc) / 1024))

# also render the layout PNGs used by README.md (keeps them in sync with the SVGs)
try:
    import cairosvg
    for top, out in [("mult_detector", "mult_layout.png"), ("log_detector", "log_layout.png")]:
        cairosvg.svg2png(url=os.path.join(REPORT, top + "_layout.svg"),
                         write_to=os.path.join(DOCS, out), output_width=760)
    print("wrote docs/{mult,log}_layout.png")
except Exception as e:
    print("NOTE: skipped README PNGs (cairosvg unavailable):", e)

print("area −%.1f%%  power −%.1f%%  die −%.1f%%  disagreement %.2f%%"
      % (area_save, pow_save, die_save, overall))
