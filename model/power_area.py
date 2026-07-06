#!/usr/bin/env python3
"""
Phase 6 -- power + area estimate for both synthesized netlists.

Since OpenSTA is not installed, use an analytic switching-energy model:

    E_op = alpha * (1 + wire) * Ctot * Vdd^2            [pJ]
    P    = E_op * f                                     (P[uW] = E_op[pJ] * f[MHz])

where Ctot = sum over all instantiated standard cells of that cell's total
INPUT-pin capacitance (read directly from the sky130 liberty, units pF), i.e.
the total node capacitance that can switch.  Assumptions (stated):

    Vdd  = 1.8 V         (tt_025C_1v80 corner)
    alpha= 0.15          activity factor (avg fraction of nodes toggling / cycle)
    wire = 1.0           wire cap ~= 1.0x cell pin cap
    f    = 50 MHz

This is an ESTIMATE.  The robust, assumption-independent figure is the
Design2/Design1 RATIO (x baseline), reported alongside the absolutes.
"""
import re, os, csv

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(HERE)
SYNTH  = os.path.join(ROOT, "synth")
REPORT = os.path.join(ROOT, "report")
LIB    = os.path.join(SYNTH, "sky130_fd_sc_hd__tt_025C_1v80.lib")

VDD   = 1.8
ALPHA = 0.15
WIRE  = 1.0
FREQ_MHZ = 50.0

# ---------------------------------------------------------------------------
# Parse liberty: per cell, sum of INPUT-pin capacitances (pF).
# ---------------------------------------------------------------------------
def parse_liberty_input_caps(path):
    cell_re = re.compile(r'^\s*cell\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)')
    pin_re  = re.compile(r'^\s*pin\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)')
    dir_re  = re.compile(r'^\s*direction\s*:\s*"?(\w+)"?')
    cap_re  = re.compile(r'^\s*capacitance\s*:\s*([0-9.eE+-]+)')
    caps = {}
    depth = 0
    cur_cell = None
    cur_pin = None; pin_depth = None; pin_dir = None; pin_cap = None
    with open(path) as f:
        for line in f:
            mcell = cell_re.match(line)
            if mcell and depth == 1:
                cur_cell = mcell.group(1); caps.setdefault(cur_cell, 0.0)
            mpin = pin_re.match(line)
            if mpin and cur_cell is not None:
                cur_pin = mpin.group(1); pin_depth = depth
                pin_dir = None; pin_cap = None
            md = dir_re.match(line)
            if md and cur_pin is not None and pin_dir is None:
                pin_dir = md.group(1)
            mc = cap_re.match(line)
            if mc and cur_pin is not None and pin_cap is None:
                pin_cap = float(mc.group(1))
            depth += line.count('{'); depth -= line.count('}')
            if cur_pin is not None and depth <= pin_depth:
                if pin_dir == 'input' and pin_cap is not None:
                    caps[cur_cell] += pin_cap
                cur_pin = None
            if cur_cell is not None and depth <= 1:
                cur_cell = None
    return caps

# ---------------------------------------------------------------------------
# Parse a gate-level netlist: histogram of sky130 cell instances.
# ---------------------------------------------------------------------------
def parse_netlist_cells(path):
    inst_re = re.compile(r'^\s*(sky130_fd_sc_hd__\w+)\s+\S+\s*\(')
    hist = {}
    with open(path) as f:
        for line in f:
            m = inst_re.match(line)
            if m:
                hist[m.group(1)] = hist.get(m.group(1), 0) + 1
    return hist

def chip_area(log_path, top):
    val = None
    with open(log_path) as f:
        for line in f:
            if "Chip area for module" in line and top in line:
                val = float(line.strip().split(":")[-1])
    return val

def energy_of(hist, caps):
    ctot = 0.0
    missing = []
    for cell, n in hist.items():
        if cell in caps:
            ctot += n * caps[cell]
        else:
            missing.append(cell)
    e_op = ALPHA * (1.0 + WIRE) * ctot * VDD * VDD      # pJ  (caps in pF)
    return ctot, e_op, missing

def read_disagreement():
    p = os.path.join(REPORT, "model_accuracy.txt")
    with open(p) as f:
        for line in f:
            m = re.search(r'OVERALL disagreement rate =.*=\s*([0-9.]+)\s*%', line)
            if m:
                return float(m.group(1))
    return None

def read_k():
    p = os.path.join(REPORT, "model_accuracy.txt")
    with open(p) as f:
        for line in f:
            m = re.search(r'\bK=(\d+)\b', line)
            if m:
                return int(m.group(1))
    return 1

def main():
    caps = parse_liberty_input_caps(LIB)
    Kval = read_k()
    LOGLBL = "log K=%d" % Kval
    print("liberty: parsed input-pin caps for %d cells (e.g. nand2_1=%.5f pF, "
          "dfxtp_1=%.5f pF)" % (len(caps),
          caps.get('sky130_fd_sc_hd__nand2_1', float('nan')),
          caps.get('sky130_fd_sc_hd__dfxtp_1', float('nan'))))

    designs = [
        ("mult baseline", "mult_detector",  "mult_detector_netlist.v",  "d1_synth.log"),
        (LOGLBL,          "log_detector",   "log_detector_netlist.v",   "d2_synth.log"),
    ]
    dis = read_disagreement()

    rows = []
    base_power = None
    for label, top, netl, log in designs:
        hist = parse_netlist_cells(os.path.join(SYNTH, netl))
        ncells = sum(hist.values())
        area = chip_area(os.path.join(SYNTH, log), top)
        ctot, e_op, missing = energy_of(hist, caps)
        power_uw = e_op * FREQ_MHZ
        if missing:
            print("WARNING %s: no cap for %s" % (label, missing))
        rows.append(dict(label=label, cells=ncells, area=area, ctot=ctot,
                         e_op=e_op, power=power_uw))
        if label == "mult baseline":
            base_power = power_uw

    # attach ratios + disagreement
    for r in rows:
        r["xbase"] = r["power"] / base_power
        r["dis"]   = 0.0 if r["label"] == "mult baseline" else dis

    # write CSV
    os.makedirs(REPORT, exist_ok=True)
    csvp = os.path.join(REPORT, "power_area.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["design", "cells", "area_um2", "Ctot_pF",
                    "energy_per_op_pJ", "power_uW_at_50MHz",
                    "x_baseline_power", "disagreement_pct_vs_baseline"])
        for r in rows:
            w.writerow([r["label"], r["cells"], "%.3f" % r["area"],
                        "%.4f" % r["ctot"], "%.4f" % r["e_op"],
                        "%.4f" % r["power"], "%.4f" % r["xbase"],
                        "%.4f" % r["dis"]])
    print("wrote", csvp)

    # pretty print
    print("\nassumptions: Vdd=%.1fV  alpha=%.2f  wire=%.1fx  f=%.0fMHz\n" %
          (VDD, ALPHA, WIRE, FREQ_MHZ))
    hdr = ("%-15s %6s %11s %9s %11s %9s %10s %8s" %
           ("design", "cells", "area_um2", "Ctot_pF", "E/op_pJ",
            "P_uW", "xbaseline", "disag%"))
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print("%-15s %6d %11.2f %9.4f %11.4f %9.4f %10.4f %8.4f" %
              (r["label"], r["cells"], r["area"], r["ctot"], r["e_op"],
               r["power"], r["xbase"], r["dis"]))
    log = rows[1]; base = rows[0]
    print("\narea  : %s = %.1fx baseline  (%.1f%% smaller)" %
          (LOGLBL, log["area"]/base["area"], 100*(1-log["area"]/base["area"])))
    print("power : %s = %.3fx baseline  (%.1f%% lower)" %
          (LOGLBL, log["xbase"], 100*(1-log["xbase"])))
    print("cost  : %.2f%% disagreement vs exact" % dis)

if __name__ == "__main__":
    main()
