#!/usr/bin/env python3
"""
make_plots.py - produces every figure used in the report from REAL tool output:
  * waveforms parsed from sim/sync_fifo_ecc.vcd (Icarus Verilog dump)
  * synthesis charts from syn/synth_results.csv (Yosys)
  * an analytical reliability plot (closed-form binomial model)
  * the architecture block diagram
Run from the project root after run_regression.sh and run_synth.py.
Output: docs/figures/*.png
"""
import csv, math, os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "docs", "figures")
os.makedirs(FIG, exist_ok=True)

# validated categorical palette (fixed order) + text tokens
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
})


# ----------------------------------------------------------------------------
# VCD parsing
# ----------------------------------------------------------------------------
def read_vcd(path, scope="tb_sync_fifo_ecc"):
    ids, widths, scopes, changes = {}, {}, [], {}
    t = 0
    with open(path) as fh:
        header = True
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if header:
                if line.startswith("$scope"):
                    scopes.append(line.split()[2])
                elif line.startswith("$upscope"):
                    scopes.pop()
                elif line.startswith("$var"):
                    p = line.split()
                    w, code, name = int(p[2]), p[3], p[4]
                    if scopes == [scope] and name not in ids.values():
                        ids[code] = name; widths[name] = w
                        changes[name] = []
                elif line.startswith("$enddefinitions"):
                    header = False
                continue
            if line[0] == "#":
                t = int(line[1:]); continue
            if line[0] in "01xzXZ" and len(line) > 1 and line[1:] in ids:
                changes[ids[line[1:]]].append((t, line[0])); continue
            if line[0] in "bB":
                v, code = line[1:].split()
                if code in ids:
                    changes[ids[code]].append((t, v))
    return changes, widths


def value_at(ch, t):
    v = "x"
    for tt, vv in ch:
        if tt > t: break
        v = vv
    return v


def to_int(v):
    try: return int(v, 2)
    except ValueError: return None


def plot_waves(changes, widths, t0, t1, sigs, fname, title, ps_per_ns=1000):
    n = len(sigs)
    fig, ax = plt.subplots(figsize=(11, 0.42 * n + 0.9))
    ax.grid(False)
    for k, (name, label, fmt) in enumerate(sigs):
        y = n - 1 - k
        ch = [(t, v) for t, v in changes[name]]
        pts = [(t0, value_at(ch, t0))] + [(t, v) for t, v in ch if t0 < t < t1] + [(t1, None)]
        if widths[name] == 1:
            xs, ys = [], []
            for (ta, va), (tb, _) in zip(pts[:-1], pts[1:]):
                lv = 0.7 if va == "1" else 0.0
                xs += [ta / ps_per_ns, tb / ps_per_ns]; ys += [y + lv, y + lv]
            ax.plot(xs, ys, color=C1 if name != "clk" else INK2, lw=1.4 if name != "clk" else 0.9,
                    drawstyle="default")
        else:
            for (ta, va), (tb, _) in zip(pts[:-1], pts[1:]):
                xa, xb = ta / ps_per_ns, tb / ps_per_ns
                d = min(0.25, (xb - xa) / 3)
                ax.plot([xa, xa + d, xb - d, xb], [y + .35, y + .7, y + .7, y + .35], color=C2, lw=1)
                ax.plot([xa, xa + d, xb - d, xb], [y + .35, y, y, y + .35], color=C2, lw=1)
                iv = to_int(va)
                txt = (fmt % iv) if iv is not None else "x"
                if (xb - xa) > (len(txt) + 1) * 0.0062 * (t1 - t0) / ps_per_ns:
                    ax.text((xa + xb) / 2, y + .35, txt, ha="center", va="center", fontsize=6.5, color=INK)
        ax.text(t0 / ps_per_ns - (t1 - t0) / ps_per_ns * 0.01, y + .35, label, ha="right",
                va="center", fontsize=8.5, color=INK)
    ax.set_xlim(t0 / ps_per_ns, t1 / ps_per_ns)
    ax.set_ylim(-0.4, n)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("time (ns)")
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    for x in range(int(t0 / ps_per_ns) // 50 * 50, int(t1 / ps_per_ns) + 1, 50):
        ax.axvline(x, color=GRID, lw=0.5, zorder=0)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=170)
    plt.close(fig)


def waveforms():
    vcd = os.path.join(ROOT, "sim", "sync_fifo_ecc.vcd")
    ch, w = read_vcd(vcd)
    S1 = [("clk", "clk", ""), ("rst_n", "rst_n", ""), ("wr_en", "wr_en", ""),
          ("rd_en", "rd_en", ""), ("wr_data", "wr_data", "%08X"), ("count", "count", "%d"),
          ("full", "full", ""), ("almost_full", "almost_full", ""), ("empty", "empty", ""),
          ("almost_empty", "almost_empty", ""), ("overflow", "overflow", ""),
          ("underflow", "underflow", ""), ("rd_valid", "rd_valid", ""),
          ("rd_data", "rd_data", "%08X")]
    # window A: reset -> fill -> overflow -> start of write-through
    plot_waves(ch, w, 0, 270_000, S1, "wave_fill_overflow.png",
               "Fig. A - reset, fill to full, two blocked writes set the sticky overflow flag")
    plot_waves(ch, w, 200_000, 470_000, S1, "wave_write_through.png",
               "Fig. B - write-through: one write and one read per clock while full (count stays 16)")
    plot_waves(ch, w, 540_000, 810_000, S1, "wave_drain_underflow.png",
               "Fig. C - drain to empty, reads on empty set the sticky underflow flag")
    # window C: first ECC fault injections
    t_inj = next(t for t, v in ch["inj_en"] if v == "1")
    S3 = [("clk", "clk", ""), ("wr_en", "wr_en", ""), ("inj_en", "inj_en", ""),
          ("inj_mask", "inj_mask", "%X"), ("wr_data", "wr_data", "%08X"),
          ("rd_en", "rd_en", ""), ("rd_valid", "rd_valid", ""), ("rd_data", "rd_data", "%08X"),
          ("sec_err", "sec_err", ""), ("ded_err", "ded_err", ""), ("sec_cnt", "sec_cnt", "%d"),
          ("count", "count", "%d")]
    plot_waves(ch, w, t_inj - 20_000, t_inj + 250_000, S3, "wave_ecc_inject.png",
               "Fig. D - single-bit faults injected into stored codewords are corrected on read (sec_err, sec_cnt)")
    return t_inj


# ----------------------------------------------------------------------------
# synthesis charts
# ----------------------------------------------------------------------------
def load_syn():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "syn", "synth_results.csv"))))
    return {r["config"]: r for r in rows}


def synth_charts(s):
    depths = [8, 16, 32, 64]
    series = [("Baseline FIFO", "base", C1), ("Proposed, ECC_EN=0", "noecc", C2),
              ("Proposed, ECC_EN=1", "ecc", C3)]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bw = 0.26
    for i, (lab, key, col) in enumerate(series):
        vals = [int(s["%s_w32_d%d" % (key, d)]["cmos_transistors"]) for d in depths]
        xs = [k + (i - 1) * (bw + 0.02) for k in range(len(depths))]
        ax.bar(xs, vals, width=bw, color=col, label=lab, edgecolor="white", linewidth=1)
        for x, v in zip(xs, vals):
            ax.text(x, v + 400, "%.1fk" % (v / 1000), ha="center", va="bottom", fontsize=6.5, color=INK2)
    ax.set_xticks(range(len(depths)))
    ax.set_xticklabels(["DEPTH=%d" % d for d in depths])
    ax.set_ylabel("estimated CMOS transistors")
    ax.set_title("Synthesised area vs FIFO depth (DATA_W = 32, Yosys + ABC)", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="x", visible=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "synth_area_vs_depth.png"), dpi=170); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ov = [100.0 * (int(s["ecc_w32_d%d" % d]["cmos_transistors"]) /
                   int(s["noecc_w32_d%d" % d]["cmos_transistors"]) - 1) for d in depths]
    ax.plot(depths, ov, color=C3, lw=2, marker="o", ms=7, mec="white", mew=2)
    for d, v in zip(depths, ov):
        ax.text(d, v + 4, "%.1f %%" % v, ha="center", fontsize=8, color=INK)
    ax.axhline(100.0 * 7 / 32, color=INK2, lw=1, ls="--")
    ax.text(64, 100.0 * 7 / 32 - 8, "storage-bit floor 7/32 = 21.9 %", ha="right", fontsize=7.5, color=INK2)
    ax.set_xscale("log", base=2); ax.set_xticks(depths); ax.set_xticklabels([str(d) for d in depths])
    ax.set_ylim(0, max(ov) * 1.2)
    ax.set_xlabel("FIFO depth (words)"); ax.set_ylabel("area overhead of SECDED (%)")
    ax.set_title("Cost of ECC shrinks with depth (DATA_W = 32)", loc="left", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "ecc_overhead_vs_depth.png"), dpi=170); plt.close(fig)
    return ov


# ----------------------------------------------------------------------------
# analytical reliability model
# ----------------------------------------------------------------------------
def reliability():
    """Probability that a word read from the FIFO is wrong, given an
    independent per-bit upset probability p while the word is stored.
      unprotected 32-bit : 1-(1-p)^32
      SECDED (39,32)     : P(>=2 flips in 39 bits)  (all single flips corrected)"""
    ps = [10 ** (-x / 10.0) for x in range(20, 91)]
    un = [1 - (1 - p) ** 32 for p in ps]
    ec = [1 - (1 - p) ** 39 - 39 * p * (1 - p) ** 38 for p in ps]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.loglog(ps, un, color=C1, lw=2, label="Unprotected (32 bits)")
    ax.loglog(ps, ec, color=C3, lw=2, label="SECDED (39,32)")
    ax.text(1e-6, 1 - (1 - 1e-6) ** 32 * 1.0 + 3e-5, "unprotected", color=INK, fontsize=8)
    ax.text(1e-6, 1.4e-9, "SECDED", color=INK, fontsize=8)
    ax.set_xlabel("per-bit upset probability during storage, p")
    ax.set_ylabel("probability a read word is wrong")
    ax.set_title("Analytical silent-data-error probability per word", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "reliability_model.png"), dpi=170); plt.close(fig)
    p = 1e-6
    return (1 - (1 - p) ** 32, 1 - (1 - p) ** 39 - 39 * p * (1 - p) ** 38)


# ----------------------------------------------------------------------------
# block diagram
# ----------------------------------------------------------------------------
def block_diagram():
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 46); ax.axis("off")

    def box(x, y, w, h, txt, fc="#eef4fc", ec=C1):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                    fc=fc, ec=ec, lw=1.3))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=8.2, color=INK)

    def arrow(x0, y0, x1, y1, txt="", dy=1.0):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.1))
        if txt:
            ax.text((x0 + x1) / 2, (y0 + y1) / 2 + dy, txt, ha="center", fontsize=7, color=INK2)

    box(2, 30, 13, 7, "wr_data\n[DATA_W]", fc="white", ec=INK2)
    box(21, 30, 15, 7, "SECDED\nencoder")
    box(41, 30, 9, 7, "XOR\ninject", fc="#fdf0ea", ec=C2)
    box(56, 24, 17, 19, "Storage array\nDEPTH x CW_W\n(CW_W = DATA_W\n + PAR_W + 1)", fc="#eaf7f1", ec=C3)
    box(78, 30, 8.5, 7, "read\nregister")
    box(90, 30, 9.5, 7, "SECDED\ndecoder")
    box(41, 40, 9, 4.5, "inj_en,\ninj_mask", fc="white", ec=INK2)
    arrow(15.3, 33.5, 20.7, 33.5)
    arrow(36.3, 33.5, 40.7, 33.5, "CW_W")
    arrow(45.5, 40, 45.5, 37.3)
    arrow(50.3, 33.5, 55.7, 33.5)
    arrow(73.3, 33.5, 77.7, 33.5)
    arrow(86.8, 33.5, 89.7, 33.5)
    ax.text(94.7, 27.3, "rd_data, sec_err,\nded_err", ha="center", va="top", fontsize=7.5, color=INK)

    box(2, 9, 18, 9, "Handshake\nwr_fire = wr_en &\n  (~full | rd_en)\nrd_fire = rd_en & ~empty", fc="white", ec=INK2)
    box(25, 9, 15, 9, "wr_ptr / rd_ptr\n(ADDR_W bits)")
    box(45, 9, 15, 9, "occupancy\ncount_nxt =\ncount + wr - rd")
    box(65, 9, 17, 9, "registered flags\nfull, empty,\nalmost_full >= AF,\nalmost_empty <= AE")
    box(86, 9, 13.5, 9, "status: overflow,\nunderflow (sticky),\nsec_cnt, ded_cnt\n(saturating)", fc="#fdf0ea", ec=C2)
    arrow(20.3, 13.5, 24.7, 13.5)
    arrow(40.3, 13.5, 44.7, 13.5)
    arrow(60.3, 13.5, 64.7, 13.5)
    arrow(82.3, 13.5, 85.7, 13.5)
    arrow(32.5, 18.3, 58, 23.7, "addresses", dy=1.8)
    arrow(94.7, 29.7, 94.7, 27.8)
    ax.text(73.5, 4.5, "af_thresh, ae_thresh (run-time programmable)", ha="center", fontsize=7.5, color=INK2)
    ax.text(50, 45.5, "sync_fifo_ecc - proposed architecture (single clock domain)",
            ha="center", fontsize=10, color=INK, weight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "block_diagram.png"), dpi=170); plt.close(fig)


if __name__ == "__main__":
    block_diagram()
    t = waveforms()
    s = load_syn()
    ov = synth_charts(s)
    un, ec = reliability()
    print("figures written to", FIG)
    print("first injection at %.1f ns" % (t / 1000))
    print("ECC overhead vs depth:", ["%.1f%%" % v for v in ov])
    print("p=1e-6: unprotected %.3e, SECDED %.3e, improvement x%.0f" % (un, ec, un / ec))
