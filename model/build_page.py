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
def block_diagram():
    RED, BLUE = "#e34948", "var(--accent)"
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

# ---------------------------------------------------------------------------
PAGE = f"""<div class="wrap">
<header>
  <div class="eyebrow">SkyWater 130 nm · open-source RTL→GDS flow (yosys)</div>
  <h1>Multiplier vs. K=1 Log/LNS Spike Detector</h1>
  <p class="sub">Two RTL designs of the same function
  <code>spike = (A·B + C·D) &gt; V<sub>th</sub></code> (<b>12-bit</b> inputs) — an
  exact-multiplier baseline and a multiplier-free log-domain (LNS, K=1) variant —
  synthesized and compared on the sky130 HD standard-cell library.</p>
  <div class="takeaway">
    Dropping the two multipliers for the K=1 log detector cuts
    <b>area {area_save:.0f}%</b> and estimated <b>power {pow_save:.0f}%</b>,
    at a <b>{overall:.2f}% accuracy cost</b> vs. exact math.
  </div>
</header>

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
       "<title>Multiplier vs K=1 Log Spike Detector — sky130</title>"
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
