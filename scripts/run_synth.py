#!/usr/bin/env python3
"""
run_synth.py - logic synthesis of every design configuration with Yosys.

Flow per configuration (technology-independent, reproducible, open-source):
    read_verilog -defer  ->  chparam  ->  hierarchy  ->  synth -flatten
    -> abc to a 2-input generic gate set + MUX  ->  stat (+ -tech cmos)  ->  ltp
Results:
    syn/reports/<cfg>.rpt     full Yosys log for each configuration
    syn/synth_results.csv     cells / flip-flops / CMOS transistor estimate /
                              logic depth (longest combinational path in gates)
Run from the project root:  python3 scripts/run_synth.py
Needs either a native `yosys` binary on PATH or the `pyosys` Python wheel
(pip install pyosys), which bundles libyosys and yosys-abc.
"""
import csv, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOSYS_BIN = shutil.which("yosys")


def yosys_cmd(cmds):
    """Command line that runs a Yosys script: native binary, else pyosys."""
    if YOSYS_BIN:
        return [YOSYS_BIN, "-p", cmds]
    code = ("from pyosys import libyosys as ys; import sys; "
            "ys.run_pass(sys.argv[1], ys.Design())")
    return [sys.executable, "-c", code, cmds]
OUT = os.path.join(ROOT, "syn")
RPT = os.path.join(OUT, "reports")
ECC_RTL = ["rtl/sync_fifo_ecc.v", "rtl/secded_enc.v", "rtl/secded_dec.v"]

CONFIGS = []
for d in (8, 16, 32, 64):
    CONFIGS.append(("base_w32_d%d" % d, "fifo_baseline", ["rtl/fifo_baseline.v"],
                    {"DATA_W": 32, "DEPTH": d}))
    CONFIGS.append(("noecc_w32_d%d" % d, "sync_fifo_ecc", ECC_RTL,
                    {"DATA_W": 32, "DEPTH": d, "ECC_EN": 0}))
    CONFIGS.append(("ecc_w32_d%d" % d, "sync_fifo_ecc", ECC_RTL,
                    {"DATA_W": 32, "DEPTH": d, "ECC_EN": 1}))
for w in (8, 16, 64):
    CONFIGS.append(("base_w%d_d16" % w, "fifo_baseline", ["rtl/fifo_baseline.v"],
                    {"DATA_W": w, "DEPTH": 16}))
    CONFIGS.append(("ecc_w%d_d16" % w, "sync_fifo_ecc", ECC_RTL,
                    {"DATA_W": w, "DEPTH": 16, "ECC_EN": 1}))
for w in (8, 16, 32, 64):
    CONFIGS.append(("enc_w%d" % w, "secded_enc", ["rtl/secded_enc.v"], {"DATA_W": w}))
    CONFIGS.append(("dec_w%d" % w, "secded_dec", ["rtl/secded_dec.v"], {"DATA_W": w}))

GATES = "AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX"


def script(top, files, params):
    s = ["read_verilog -defer " + " ".join(os.path.join(ROOT, f) for f in files)]
    for k, v in params.items():
        s.append("chparam -set %s %d %s" % (k, v, top))
    s += ["hierarchy -check -top %s" % top,
          "synth -flatten -top %s" % top,
          "abc -g %s" % GATES,
          "opt_clean -purge",
          "tee -o /dev/null check -assert",
          "stat",
          "stat -tech cmos",
          "ltp -noff"]
    return "; ".join(s)


def parse(log):
    """Extract numbers from the last two `stat` blocks (plain, -tech cmos)."""
    blocks = log.split("Printing statistics")
    plain, cmos = blocks[-2], blocks[-1]
    plain = plain.split("Executing")[0]
    m = re.search(r"\n\s+([\d,]+)\s+cells\s*\n", plain)
    cells = int(m.group(1).replace(",", "")) if m else None
    m = re.search(r"[Ee]stimated number of transistors:\s+([\d,]+)", cmos)
    trans = int(m.group(1).replace(",", "")) if m else None
    m = re.findall(r"Longest topological path in \S+ \(length=(\d+)\)", log)
    depth = int(m[-1]) if m else None
    ffs = sum(int(n) for n, c in
              re.findall(r"\n\s+(\d+)\s+(\$_\S*DFF\S*)", plain))
    gates = {}
    for n, c in re.findall(r"\n\s+(\d+)\s+\$_([A-Z]+)_\s*(?=\n)", plain):
        gates[c] = gates.get(c, 0) + int(n)
    return cells, ffs, trans, depth, gates


def main():
    os.makedirs(RPT, exist_ok=True)
    if YOSYS_BIN:
        ver = subprocess.run([YOSYS_BIN, "-V"], capture_output=True, text=True).stdout.strip()
    else:
        from pyosys import libyosys as ys
        ver = ys.yosys_maybe_version() + " (via pyosys)"
    rows = []
    for name, top, files, params in CONFIGS:
        r = subprocess.run(yosys_cmd(script(top, files, params)),
                           capture_output=True, text=True)
        log = r.stdout + r.stderr
        open(os.path.join(RPT, name + ".rpt"), "w").write(log)
        if r.returncode != 0:
            raise SystemExit("Yosys failed on %s, see %s.rpt" % (name, name))
        cells, ffs, trans, depth, gates = parse(log)
        logic = cells - ffs
        rows.append([name, top] + [params.get(k, "") for k in ("DATA_W", "DEPTH", "ECC_EN")]
                    + [cells, ffs, logic, trans, depth,
                       gates.get("XOR", 0) + gates.get("XNOR", 0), gates.get("MUX", 0)])
        print("%-16s cells=%6s ff=%5s logic=%6s trans=%7s depth=%3s"
              % (name, cells, ffs, logic, trans, depth))
    with open(os.path.join(OUT, "synth_results.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["config", "top", "DATA_W", "DEPTH", "ECC_EN", "cells", "flip_flops",
                    "comb_gates", "cmos_transistors", "logic_depth_gates", "xor_xnor", "mux"])
        w.writerows(rows)
    open(os.path.join(OUT, "tool_version.txt"), "w").write(ver + "\n")


if __name__ == "__main__":
    main()
