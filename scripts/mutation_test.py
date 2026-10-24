#!/usr/bin/env python3
"""
mutation_test.py - checks that the testbench is strong enough to detect bugs.

Each mutant injects one deliberate, realistic design bug into a temporary copy
of the RTL, re-runs the self-checking testbench, and records whether the
testbench reported FAIL ("killed") or still PASSed ("survived").
A good testbench kills every mutant.

Usage:  python3 scripts/mutation_test.py        (run from the project root)
Output: sim/logs/mutation_report.txt, sim/logs/mutation_results.csv
"""
import csv, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RTL = ["sync_fifo_ecc.v", "secded_enc.v", "secded_dec.v"]
TB = os.path.join(ROOT, "tb", "tb_sync_fifo_ecc.v")

# (id, description, file, original text, mutated text, extra plusargs)
MUTANTS = [
    ("M1", "write-through-when-full removed",          "sync_fifo_ecc.v",
     "wr_en & (~full | rd_en)", "wr_en & ~full", ""),
    ("M2", "almost_full uses > instead of >=",         "sync_fifo_ecc.v",
     "(count_nxt >= af_thresh)", "(count_nxt > af_thresh)", ""),
    ("M3", "almost_empty uses < instead of <=",        "sync_fifo_ecc.v",
     "(count_nxt <= ae_thresh)", "(count_nxt < ae_thresh)", ""),
    ("M4", "occupancy ignores reads",                  "sync_fifo_ecc.v",
     "- {{ADDR_W{1'b0}}, rd_fire}", "", ""),
    ("M5", "read pointer advances on rd_en (not rd_fire)", "sync_fifo_ecc.v",
     "if (rd_fire) begin\n                rd_ptr    <= rd_ptr + 1'b1;",
     "if (rd_en) rd_ptr <= rd_ptr + 1'b1;\n            if (rd_fire) begin", ""),
    ("M6", "overflow flag not sticky-set",             "sync_fifo_ecc.v",
     "overflow  <= 1'b1;", "overflow  <= 1'b0;", ""),
    ("M7", "underflow detection removed",              "sync_fifo_ecc.v",
     "if (rd_en &  empty)                underflow <= 1'b1;", "", ""),
    ("M8", "status clear does not clear counters",     "sync_fifo_ecc.v",
     "end else if (clr_status) begin\n            overflow  <= 1'b0;\n            underflow <= 1'b0;\n            sec_cnt   <= 16'd0;\n            ded_cnt   <= 16'd0;",
     "end else if (clr_status) begin\n            overflow  <= 1'b0;\n            underflow <= 1'b0;", ""),
    ("M9", "SEC counter does not saturate (wraps)",    "sync_fifo_ecc.v",
     "if (sec_err && (sec_cnt != 16'hFFFF))", "if (sec_err)", "+sat"),
    ("M10", "full flag one entry early",               "sync_fifo_ecc.v",
     "(count_nxt == DEPTH_V)", "(count_nxt == DEPTH_V - 1'b1)", ""),
    ("M11", "decoder does not correct single errors",  "secded_dec.v",
     "if (syn_i == i) fixed[i] = ~fixed[i];", "if (syn_i == i) fixed[i] = fixed[i];", ""),
    ("M12", "encoder overall-parity bit stuck at 0",   "secded_enc.v",
     "c[0] = ^c[HAM_W:1];", "c[0] = 1'b0;", ""),
    ("M13", "encoder check bit uses wrong coverage",   "secded_enc.v",
     "if ((((i >> j) & 1) == 1) && (i != (1 << j)))",
     "if ((((i >> j) & 1) == 1) && (i != (1 << j)) && (i < HAM_W))", ""),
    ("M14", "DED reported as SEC (double errors miscorrected)", "secded_dec.v",
     "end else if (syn != {PAR_W{1'b0}}) begin\n            ded_o = 1'b1;",
     "end else if (syn != {PAR_W{1'b0}}) begin\n            sec_o = 1'b1;", ""),
    ("M15", "rd_valid asserted on rd_en (not rd_fire)", "sync_fifo_ecc.v",
     "rd_valid     <= rd_fire;", "rd_valid     <= rd_en;", ""),
]


def run(workdir, plusargs):
    vvp = os.path.join(workdir, "m.vvp")
    srcs = [TB] + [os.path.join(workdir, f) for f in RTL]
    r = subprocess.run(["iverilog", "-g2005", "-P", "tb_sync_fifo_ecc.N_RAND=6000",
                        "-o", vvp] + srcs, capture_output=True, text=True)
    if r.returncode != 0:
        return "COMPILE_ERROR", r.stderr.strip().splitlines()[:3]
    args = ["vvp", "-n", vvp] + ([plusargs] if plusargs else [])
    r = subprocess.run(args, capture_output=True, text=True, cwd=workdir, timeout=900)
    out = r.stdout
    mism = re.search(r"mismatches\s*:\s*(\d+)", out)
    first = [l for l in out.splitlines() if "MISMATCH" in l][:1]
    if "RESULT: PASS" in out:
        return "SURVIVED", first
    return "KILLED (%s mismatches)" % (mism.group(1) if mism else "?"), first


def main():
    logdir = os.path.join(ROOT, "sim", "logs")
    os.makedirs(logdir, exist_ok=True)
    rows, lines = [], []
    # sanity: unmodified design must pass
    with tempfile.TemporaryDirectory() as td:
        for f in RTL:
            shutil.copy(os.path.join(ROOT, "rtl", f), td)
        status, _ = run(td, "")
        lines.append("Golden (unmutated) design : %s" % ("PASS" if status == "SURVIVED" else status))
    killed = 0
    for mid, desc, fname, old, new, pa in MUTANTS:
        with tempfile.TemporaryDirectory() as td:
            for f in RTL:
                shutil.copy(os.path.join(ROOT, "rtl", f), td)
            p = os.path.join(td, fname)
            src = open(p).read()
            if old not in src:
                print("Mutant %s: pattern not found" % mid); sys.exit(1)
            open(p, "w").write(src.replace(old, new, 1))
            status, first = run(td, pa)
        if status.startswith("KILLED"):
            killed += 1
        rows.append([mid, desc, fname, status, first[0].strip() if first else ""])
        msg = "%-4s %-50s %s" % (mid, desc, status)
        print(msg); lines.append(msg)
        if first:
            lines.append("       first detection: " + first[0].strip())
    lines.append("")
    lines.append("Mutation score: %d / %d killed (%.1f %%)"
                 % (killed, len(MUTANTS), 100.0 * killed / len(MUTANTS)))
    print(lines[-1])
    open(os.path.join(logdir, "mutation_report.txt"), "w").write("\n".join(lines) + "\n")
    with open(os.path.join(logdir, "mutation_results.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "bug", "file", "result", "first_detection"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
