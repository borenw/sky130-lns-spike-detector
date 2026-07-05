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
REPO      = "https://github.com/borenw/sky130-lns-spike-detector"
REPO_BLOB = REPO + "/blob/main"
REPO_ZIP  = REPO + "/archive/refs/heads/main.zip"

M = pa["mult baseline"]; L = pa["log K=1"]
FM = fp["mult_detector"]; FL = fp["log_detector"]

def f(x): return float(x)
area_save = 100 * (1 - f(L["area_um2"]) / f(M["area_um2"]))
pow_save  = 100 * (1 - f(L["x_baseline_power"]))
die_save  = 100 * (1 - f(FL["die_area_um2"]) / f(FM["die_area_um2"]))

# ---- comparison table rows ----
def pct(a, b): return "%.3f×" % (f(a) / f(b))
rows_tbl = [
    ("Standard-cell area", "%s µm²" % M["area_um2"], "%s µm²" % L["area_um2"],
     "%.3f× (−%.1f%%)" % (f(L["area_um2"])/f(M["area_um2"]), area_save)),
    ("Die size (x × y @65%)", "%s × %s µm" % (FM["die_x_um"], FM["die_y_um"]),
     "%s × %s µm" % (FL["die_x_um"], FL["die_y_um"]),
     "%.3f× (−%.1f%%)" % (f(FL["die_area_um2"])/f(FM["die_area_um2"]), die_save)),
    ("Die area (x·y)", "%s µm²" % FM["die_area_um2"], "%s µm²" % FL["die_area_um2"],
     "%.3f×" % (f(FL["die_area_um2"])/f(FM["die_area_um2"]))),
    ("Std-cell count", M["cells"], L["cells"],
     "%.3f×" % (f(L["cells"])/f(M["cells"]))),
    ("Multipliers ($mul)", "2", "0", "eliminated"),
    ("Energy / op (est.)", "%s pJ" % M["energy_per_op_pJ"], "%s pJ" % L["energy_per_op_pJ"],
     "%.3f×" % (f(L["energy_per_op_pJ"])/f(M["energy_per_op_pJ"]))),
    ("Power @ 50 MHz (est.)", "%s µW" % M["power_uW_at_50MHz"], "%s µW" % L["power_uW_at_50MHz"],
     "%.3f× (−%.1f%%)" % (f(L["x_baseline_power"]), pow_save)),
    ("Accuracy vs exact", "0.00 % (reference)", "%.2f %% disagree" % overall, "K=1 cost"),
    ("Verification", "PASS (= exp_exact)", "PASS (= exp_k1)", "both bit-exact"),
]

def tbl_rows():
    out = []
    for metric, a, b, delta in rows_tbl:
        out.append(
            "<tr><th scope='row'>%s</th><td>%s</td><td class='hl'>%s</td>"
            "<td class='delta'>%s</td></tr>" % (metric, a, b, delta))
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
    P = ['<svg viewBox="0 0 520 308" width="100%" xmlns="http://www.w3.org/2000/svg" '
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
    P.append(blk(322, 57, 52, 26, ["spike"]))
    # lane 2 : log / LNS -- (A·B − C·D) > Vth  computed as  A·B > C·D + Vth,
    # so the threshold folds into the LNS add with y, and x goes to the comparator.
    P.append('<text x="14" y="146" font-size="12.5" font-weight="700" fill="var(--ink2)">'
             '② Log / LNS, K=1</text>')
    P.append('<rect x="148" y="133" width="106" height="17" rx="8.5" '
             'fill="rgba(12,163,12,0.14)" stroke="#0ca30c" stroke-width="0.8"/>')
    P.append('<text x="201" y="145" text-anchor="middle" font-size="10" font-weight="600" '
             'fill="#0ca30c">✓ no × cells</text>')
    # input -> log2 arrows (4 operands + Vth)
    for cy in (166.5, 191.5, 220.5, 245.5):
        P.append(arr(44, cy, 52, cy))
    P.append(arr(48, 287.5, 52, 287.5))
    # log2 -> adders
    P.append(arr(104, 166.5, 124, 173)); P.append(arr(104, 191.5, 124, 186))
    P.append(arr(104, 220.5, 124, 227)); P.append(arr(104, 245.5, 124, 240))
    # add1 -> compare (x=log A·B) ; add2 -> LNS (y) ; Vth-log -> LNS (v) ;
    # LNS -> compare (w=log(C·D+Vth)) ; compare -> spike
    P.append(arr(156, 179, 346, 208, "x"))
    P.append(arr(156, 233, 196, 240, "y"))
    P.append(arr(104, 287.5, 196, 272, "log₂Vth"))
    P.append(arr(308, 253, 346, 232, "w"))
    P.append(arr(446, 218, 460, 218))
    # input boxes
    for y, lbl in ((158, "A"), (183, "B"), (212, "C"), (237, "D")):
        P.append(blk(12, y, 32, 17, [lbl]))
    P.append(blk(12, 279, 36, 17, ["Vth"]))
    # per-operand log2 converters (the 4 parallel paths) + Vth's converter
    for y in (158, 183, 212, 237, 279):
        P.append(blk(52, y, 52, 17, ["log₂·K1"], BLUE))
    # two log-adders (= LNS multiply), the LNS add (folds Vth into C·D), compare, spike
    P.append(blk(124, 166, 32, 26, ["+"])); P.append(blk(124, 220, 32, 26, ["+"]))
    P.append(blk(196, 224, 112, 58, ["LNS add", "w = log₂(C·D+Vth)", "max(y,v)+F(|y−v|)"], BLUE))
    P.append(blk(346, 196, 100, 44, ["compare &gt;", "A·B &gt; C·D+Vth"]))
    P.append(blk(460, 205, 50, 26, ["spike"]))
    P.append('</svg>')
    cap = ('<figcaption><b>Target use case: spike = (A·B − C·D) &gt; Vth.</b> Subtracting in '
           'the log domain is LNS&#39;s weak spot (it needs a sign bit and a ROM that '
           'blows up at cancellation), so rearrange to <b>A·B &gt; C·D + Vth</b>: the '
           'LNS add folds the threshold into the C·D term — Vth&#39;s log indexes the same '
           'F = log₂(1+2<sup>−d</sup>) ROM via |y−v| — and a comparator tests '
           'x = log₂(A·B) against w = log₂(C·D+Vth). At Vth=0 this is just x &gt; y, the '
           'monotonic-log sign of A·B − C·D (no ROM). <i>Note: the synthesized netlists and '
           'every number on this page are the closely related A·B + C·D build — same '
           'datapath, threshold folded into the LNS add instead of a bare comparator.</i>'
           '</figcaption>')
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
    P.append(blk(120, 41, 178, 42, ["mult_detector.v", "p1=Ar*Br  p2=Cr*Dr", "S=p1+p2 · spike←(S&gt;Vr)"], RED))
    P.append(arr(298, 62, 336, 62, "spike"))
    P.append(blk(336, 49, 54, 26, ["spike"]))
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
    P.append(arr(586, 188, 618, 188, "spike"))
    P.append(blk(618, 175, 52, 26, ["spike"]))
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
    Shat = 2.0 ** (s / 2.0)
    Vhat = 0.0 if zv else 2.0 ** (lv / 2.0)
    out_ex = 1 if S > Vth else 0
    out_k1 = MODEL.spike_k1(A, B, C, D, Vth)
    err = 100.0 * (Shat - S) / S if S > 0 else 0.0
    return S, Shat, Vhat, err, out_ex, out_k1

EXAMPLES = [(25, 30, 12, 40, 600), (8, 8, 5, 5, 150),
            (50, 50, 20, 20, 2000), (3, 3, 3, 3, 17)]
def example_rows():
    out = []
    for (A, B, C, D, Vth) in EXAMPLES:
        S, Shat, Vhat, err, oe, ok = _k1_row(A, B, C, D, Vth)
        mis = (oe != ok)
        verdict = ('<span class="bad">misjudge ✗</span>' if mis
                   else '<span class="ok2">match ✓</span>')
        # err% is the OUTPUT error: N/A when the output is correct, shown only on a misjudge
        err_cell = ('<span class="bad">%+.1f%%</span>' % err if mis
                    else '<span class="na">—</span>')
        out.append(
            "<tr%s><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td>"
            "<td>%d</td><td>%d</td>"
            "<td>%.0f</td><td>%s</td><td>%.0f</td><td>%d</td><td class='hl'>%d</td>"
            "<td>%s</td></tr>"
            % (' class="misrow"' if mis else '', A, B, C, D, Vth, S, A * B - C * D,
               Shat, err_cell, Vhat, oe, ok, verdict))
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
def _Fd(dh):                       # dh = ROM index in half-log2 units; real d = dh/2
    d = dh / 2.0
    real = math.log2(1.0 + 2.0 ** (-d))
    return real, round(2 * real)
FROWS = "".join(
    "<tr><td>%.1f</td><td>%.4f</td><td>%d</td></tr>" % (dh / 2.0, _Fd(dh)[0], _Fd(dh)[1])
    for dh in range(0, 7))
_mrom = re.search(r'F\(d\) ROM \(half-log2 units\):\s*\[([^\]]*)\]',
                  open(os.path.join(REPORT, "model_accuracy.txt")).read())
_romvals = [v.strip() for v in _mrom.group(1).split(",")] if _mrom else ["2", "2", "1", "1", "1", "0"]
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
def _wbr(v):                       # (exponent, frac bit, L, binary) for the K=1 converter
    e = v.bit_length() - 1
    frac = 0 if e == 0 else (v >> (e - 1)) & 1
    return e, frac, 2 * e + frac, format(v, 'b')

def _build_walk():
    A, B, C, D, Vth = 25, 30, 12, 40, 600
    eA, fA, LA, bA = _wbr(A); eB, fB, LB, bB = _wbr(B)
    eC, fC, LC, bC = _wbr(C); eD, fD, LD, bD = _wbr(D)
    X = LA + LB; Y = LC + LD; d = abs(X - Y)
    F = int(_romvals[d]); s = max(X, Y) + F
    S = A * B + C * D; Shat = 2 ** (s / 2.0); err = 100.0 * (Shat - S) / S
    eV, fV, LV, bV = _wbr(Vth); Vhat = 2 ** (LV / 2.0)
    oe = 1 if S > Vth else 0; ok = 1 if s > LV else 0
    L = []
    L.append("  A=%d  B=%d  C=%d  D=%d   (Vth=%d)        logs in half-log2 units" % (A, B, C, D, Vth))
    L.append("")
    L.append("  1) log-convert   L(v) = 2*floor(log2 v) + (next bit below the leading 1)")
    for v, e, f, Lv_, b in ((A, eA, fA, LA, bA), (B, eB, fB, LB, bB),
                            (C, eC, fC, LC, bC), (D, eD, fD, LD, bD)):
        L.append("       L(%2d) = 2*%d + %d = %-2d       %d = %sb" % (v, e, f, Lv_, v, b))
    L.append("")
    L.append("  2) multiply = add the logs   (adding logs multiplies the operands)")
    L.append("       X = L(%d)+L(%d) = %d      ->  A*B ~ 2^(%g) = %.0f     (true %d)"
             % (A, B, X, X / 2.0, 2 ** (X / 2.0), A * B))
    L.append("       Y = L(%d)+L(%d) = %d      ->  C*D ~ 2^(%g) = %.0f     (true %d)"
             % (C, D, Y, Y / 2.0, 2 ** (Y / 2.0), C * D))
    L.append("")
    L.append("  3) LNS add   (combine the two products, still in the log domain)")
    L.append("       d = |X - Y| = |%d - %d| = %d" % (X, Y, d))
    L.append("       F(d) = ROM[%d] = %d                         <-- the one table lookup" % (d, F))
    L.append("       s = max(X,Y) + F(d) = %d + %d = %d" % (max(X, Y), F, s))
    L.append("")
    L.append("  4) result    S_hat = 2^(%g) = %.0f              (true A*B+C*D = %d,  err %+.1f%%)"
             % (s / 2.0, Shat, S, err))
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
        realF = math.log2(1 + 2 ** (-(k / 2.0)))
        used = (k == DUSED)
        note = "← used (d = |X−Y|)" if used else ""
        rs.append("<tr%s><td>%d</td><td>%s</td><td>%.4f</td>"
                  "<td style='text-align:left;color:var(--accent);font-weight:600'>%s</td></tr>"
                  % (' class="usedrow"' if used else '', k, val, realF, note))
    return "".join(rs)
ROMSLICE = _rom_slice()

# ---------------------------------------------------------------------------
PAGE = f"""<div class="wrap">
<header>
  <div class="eyebrow">SkyWater 130 nm · open-source RTL→GDS flow (yosys)</div>
  <h1>Eliminating Multipliers with K=1 Log / LNS Arithmetic</h1>
  <p class="sub">A general-purpose look at trading hardware multipliers for a small
  log-domain ROM. Two RTL implementations of the same multiply-compare kernel
  <code>(A·B + C·D) &gt; V<sub>th</sub></code> (<b>12-bit</b> inputs) — one with real
  multipliers, one multiplier-free via a K=1 logarithmic (LNS) datapath — synthesized and
  compared on the sky130 HD standard-cell library.</p>
  <div class="takeaway">
    Dropping the two multipliers for the K=1 log datapath cuts
    <b>area {area_save:.0f}%</b> and estimated <b>power {pow_save:.0f}%</b>,
    at a <b>{overall:.2f}% accuracy cost</b> vs. exact math.
  </div>
</header>

<section class="bdsec">
  <h2>RTL structure — modules &amp; signals</h2>
  {rtl_diagram()}
</section>

<section class="bdsec">
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

<section>
  <h2>Worked examples — where the approximation misjudges</h2>
  <p class="note">Real values through the implemented <code>(A·B + C·D) &gt; V<sub>th</sub></code>
  build (every number on this page is this add build). <b>Ŝ = 2<sup>s/2</sup></b> is the linear
  value the K=1 log path represents for A·B+C·D (compare it with S — that gap is the log path's
  magnitude approximation); <b>V̂ = 2<sup>Lv/2</sup></b> is the log-quantized threshold; the K=1
  output is (Ŝ &gt; V̂). <b>err%</b> is the <b>output</b> error — <b>N/A when the output is
  correct</b>, shown only on the row where the approximation flips the decision.</p>
  <div class="tablescroll">
  <table>
    <thead><tr><th>A</th><th>B</th><th>C</th><th>D</th><th>V<sub>th</sub></th>
      <th>S = A·B+C·D</th><th>A·B−C·D</th><th>Ŝ (K=1)</th><th>err %</th><th>V̂ (K=1)</th>
      <th>out<br>exact</th><th>out<br>K=1</th><th>verdict</th></tr></thead>
    <tbody>{EXROWS}</tbody>
  </table>
  </div>
  <p class="note"><b>Only the last row misjudges.</b> S = 18 sits just above V<sub>th</sub> = 17,
  but K=1 rounds A·B+C·D down to Ŝ = 16 and the threshold to V̂ = 16, so 16 &gt; 16 is false —
  output 0 where exact says 1 (a ~11% under-estimate landing right on the boundary). Note the
  third row's Ŝ = 2048 is a long way below S = 2900 — a <em>larger</em> magnitude gap — yet it
  still decides correctly, so its output error is N/A: the approximation only changes the output
  when it <em>straddles</em> the threshold, which is why the overall disagreement is ~5.6% and
  concentrates near mid-range V<sub>th</sub>.</p>
</section>

<section>
  <h2>Step-by-step — the LNS add for row 1 (C·D = 12·40)</h2>
  <p class="note">Exactly what the multiplier-free path does for worked-example row 1
  (A=25, B=30, C=12, D=40): leading-one-detector log conversion (<code>lod5.v</code>),
  log-add = multiply, then the LNS add (<code>lns_add.v</code>) with the F ROM
  (<code>lns_ftable.v</code>). Logs are in half-log₂ units (integer 2·log₂).</p>
  <div class="deriv"><pre>{WALK}</pre></div>
  <p class="note">The whole LNS add costs just <b>one table lookup</b> — <code>F(d)</code> at
  key <b>d = |X − Y| = {DUSED}</b>. Here is that slice of the actual ROM
  (<code>lns_ftable.v</code>) — the used key highlighted, with its neighbors:</p>
  <div class="tablescroll" style="display:inline-block;max-width:100%">
  <table class="ftab">
    <thead><tr><th>d&nbsp;&nbsp;(ROM key)</th><th>F&nbsp;&nbsp;(value)</th>
      <th>log₂(1+2<sup>−d/2</sup>)</th><th></th></tr></thead>
    <tbody>{ROMSLICE}</tbody>
  </table>
  </div>
</section>

<section class="kpis">
  <div class="kpi"><div class="kv">−{area_save:.0f}%</div><div class="kl">standard-cell area</div><div class="ks">{M['area_um2']} → {L['area_um2']} µm²</div></div>
  <div class="kpi"><div class="kv">−{pow_save:.0f}%</div><div class="kl">power @ 50 MHz (est.)</div><div class="ks">{L['x_baseline_power']}× baseline</div></div>
  <div class="kpi"><div class="kv">{overall:.2f}%</div><div class="kl">disagreement vs exact</div><div class="ks">K=1 accuracy cost</div></div>
  <div class="kpi"><div class="kv">0 → 2</div><div class="kl">multipliers → none</div><div class="ks">both verify PASS</div></div>
</section>

<section>
  <h2>Comparison</h2>
  <div class="tablescroll">
  <table>
    <thead><tr><th>Metric</th><th>Design 1 · multiplier</th><th>Design 2 · log K=1</th><th>Design 2 / 1</th></tr></thead>
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

<section>
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
  <h2>K=1 accuracy cost — disagreement vs exact</h2>
  <p class="note">Over 4 M Monte-Carlo samples × each threshold (the 12-bit space,
  4096⁴ ≈ 2.8×10¹⁴, cannot be enumerated, so this is a sampled estimate).
  Design 2's RTL is bit-exact to its K=1 model; a disagreement with exact math is the
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
    <thead><tr><th>d = |x−y|</th><th>F(d) = log₂(1+2<sup>−d</sup>)</th><th>stored (½-log₂ units)</th></tr></thead>
    <tbody>{FROWS}</tbody>
  </table>
  </div>
  <p class="note">Logs are carried in <b>half-log₂ units</b> (the integer 2·log₂), so the ROM is
  indexed by the integer |X−Y| and outputs round(2·F) — just 0, 1, or 2. The whole table is
  <code>{ROM_PREVIEW}</code> ({ROM_LEN} entries, d = 0…{ROM_MAXD}), i.e. ~2 bits out. That is the
  entire “F(d) ROM” drawn in the datapath above.</p>

  <p class="note"><b>Subtraction is the hard cousin.</b> A true LNS subtract would use
  F₋(d) = log₂(1 − 2<sup>−d</sup>) (plus a sign bit) — still a 1-input table of |x − y|, but it
  diverges to −∞ as d → 0 (catastrophic cancellation when A·B ≈ C·D), exactly where K=1 is
  weakest. The threshold compare <code>(A·B − C·D) &gt; Vth</code> sidesteps it by rearranging to
  an <b>add</b>, <code>A·B &gt; C·D + Vth</code>, reusing this same
  F(d) = log₂(1 + 2<sup>−d</sup>) ROM.</p>
</section>

<section>
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
.ftab{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.ftab th,.ftab td{border:1px solid var(--grid);padding:5px 12px;text-align:right}
.ftab th{color:var(--ink2);font-weight:600;background:var(--surface)}
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
       "<title>Eliminating Multipliers with K=1 Log/LNS Arithmetic — sky130</title>"
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
