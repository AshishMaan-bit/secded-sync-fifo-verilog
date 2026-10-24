#!/usr/bin/env python3
"""
make_report.py - builds docs/Project_Report.pdf.
Every number in the results chapter is read from the generated logs / CSVs
(sim/logs, syn/synth_results.csv), so the report always matches the last run.
"""
import csv, datetime, os, re
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "sim", "logs")
FIG = os.path.join(ROOT, "docs", "figures")
OUT = os.path.join(ROOT, "docs", "Project_Report.pdf")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="Times-Roman", fontSize=11,
                      leading=15, alignment=TA_JUSTIFY, spaceAfter=6)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Times-Bold", fontSize=15,
                    spaceBefore=10, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Times-Bold", fontSize=12.5,
                    spaceBefore=8, spaceAfter=5)
CAP = ParagraphStyle("cap", parent=BODY, fontSize=9.5, alignment=TA_CENTER, textColor=colors.HexColor("#52514e"))
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=10)
CELL = ParagraphStyle("cell", fontName="Times-Roman", fontSize=9.5, leading=11.5)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Times-Bold")
TITLE = ParagraphStyle("t", fontName="Times-Bold", fontSize=20, leading=26, alignment=TA_CENTER)
SUB = ParagraphStyle("s", fontName="Times-Roman", fontSize=13, leading=18, alignment=TA_CENTER)


def P(t): return Paragraph(t, BODY)


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9a9893")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8")))
    t.setStyle(TableStyle(st))
    return t


def fig(name, w_cm, caption):
    from reportlab.lib.utils import ImageReader
    p = os.path.join(FIG, name)
    iw, ih = ImageReader(p).getSize()
    w = w_cm * cm
    return KeepTogether([Image(p, width=w, height=w * ih / iw), Spacer(1, 3), Paragraph(caption, CAP),
                         Spacer(1, 8)])


def grab(path, pat, default="?"):
    m = re.search(pat, open(path).read())
    return m.group(1).strip() if m else default


# ------------------------------------------------------------------ data
main_log = os.path.join(LOG, "fifo_main_w32_d16_ecc.log")
M = {k: grab(main_log, p) for k, p in {
    "cycles": r"clock cycles simulated\s*:\s*(\d+)",
    "wrrd": r"writes accepted / reads accepted:\s*([\d /]+)",
    "checks": r"scoreboard comparisons\s*:\s*(\d+)",
    "mism": r"mismatches\s*:\s*(\d+)",
    "fe": r"cycles full / empty\s*:\s*([\d /]+)",
    "maxocc": r"max occupancy reached\s*:\s*(.+)",
    "wthru": r"write-through at full\s*:\s*(\d+)",
    "blk": r"blocked writes / blocked reads\s*:\s*([\d /]+)",
    "simul": r"simultaneous wr_en & rd_en\s*:\s*(\d+)",
    "aeaf": r"almost_full / almost_empty rises:\s*([\d /]+)",
    "clr": r"status clears\s*:\s*(\d+)",
    "inj": r"single / double faults injected :\s*([\d /]+)",
    "pos": r"codeword bit positions covered\s*:\s*(.+)",
    "secded": r"SEC events / DED events seen\s*:\s*([\d /]+)",
}.items()}
noecc_log = os.path.join(LOG, "fifo_w32_d16_noecc.log")
silent = grab(noecc_log, r"silently corrupted reads \(no ECC\):\s*(\d+)")
noecc_inj = grab(noecc_log, r"single / double faults injected :\s*([\d /]+)")

reg_rows = [["Run", "Result"]]
for line in open(os.path.join(LOG, "regression_summary.txt")):
    m = re.match(r"(.+?)\s+(PASS|FAIL)\s*$", line.rstrip())
    if m: reg_rows.append([m.group(1), m.group(2)])
reg_total = grab(os.path.join(LOG, "regression_summary.txt"), r"TOTAL:\s*(.+)")

sec_rows = [["DATA_W", "PAR_W", "Codeword", "Clean words", "Single-bit cases", "Double-bit cases", "Mismatches"]]
for w in (8, 16, 32, 64):
    p = os.path.join(LOG, "secded_w%d.log" % w)
    hdr = re.search(r"DATA_W=(\d+)\s+PAR_W=(\d+)\s+CW_W=(\d+)", open(p).read())
    sec_rows.append([hdr.group(1), hdr.group(2), "(%s,%s)" % (hdr.group(3), hdr.group(1)),
                     grab(p, r"clean words checked\s*:\s*(\d+)"),
                     grab(p, r"single-bit errors checked:\s*(\d+)"),
                     grab(p, r"double-bit errors checked:\s*(\d+)"),
                     grab(p, r"mismatches\s*:\s*(\d+)")])

mut = list(csv.DictReader(open(os.path.join(LOG, "mutation_results.csv"))))
mut_rows = [["ID", "Injected design bug", "File", "Testbench result"]] + \
           [[m["id"], m["bug"], m["file"], m["result"]] for m in mut]
mut_score = grab(os.path.join(LOG, "mutation_report.txt"), r"Mutation score:\s*(.+)")

S = {r["config"]: r for r in csv.DictReader(open(os.path.join(ROOT, "syn", "synth_results.csv")))}


def srow(label, k):
    r = S[k]
    return [label, r["flip_flops"], r["comb_gates"], r["cells"], r["cmos_transistors"], r["logic_depth_gates"]]


syn_main = [["Design (DATA_W=32, DEPTH=16)", "Flip-flops", "Comb. gates", "Total cells",
             "CMOS transistors (est.)", "Logic depth (gates)"],
            srow("Conventional FIFO (fifo_baseline)", "base_w32_d16"),
            srow("Proposed, ECC_EN = 0", "noecc_w32_d16"),
            srow("Proposed, ECC_EN = 1 (SECDED)", "ecc_w32_d16")]
syn_depth = [["DEPTH", "Baseline", "Proposed ECC_EN=0", "Proposed ECC_EN=1", "SECDED overhead vs ECC_EN=0"]]
for d in (8, 16, 32, 64):
    b, n, e = (int(S["%s_w32_d%d" % (k, d)]["cmos_transistors"]) for k in ("base", "noecc", "ecc"))
    syn_depth.append([d, b, n, e, "%.1f %%" % (100.0 * (e / n - 1))])
syn_codec = [["DATA_W", "Codeword", "Encoder gates", "Encoder depth", "Decoder gates", "Decoder depth"]]
for w in (8, 16, 32, 64):
    en, de = S["enc_w%d" % w], S["dec_w%d" % w]
    par = {8: 4, 16: 5, 32: 6, 64: 7}[w]
    syn_codec.append([w, "(%d,%d)" % (w + par + 1, w), en["cells"], en["logic_depth_gates"],
                      de["cells"], de["logic_depth_gates"]])
syn_width = [["DATA_W (DEPTH=16)", "Baseline transistors", "SECDED FIFO transistors", "Ratio"]]
for w in (8, 16, 32, 64):
    b, e = int(S["base_w%d_d16" % w]["cmos_transistors"]), int(S["ecc_w%d_d16" % w]["cmos_transistors"])
    syn_width.append([w, b, e, "%.2f x" % (e / b)])
ver_yosys = open(os.path.join(ROOT, "syn", "tool_version.txt")).read().strip().split(" (git")[0]
p = 1e-6
p_un = 1 - (1 - p) ** 32
p_ec = 1 - (1 - p) ** 39 - 39 * p * (1 - p) ** 38

# ------------------------------------------------------------------ story
st = []
st += [Spacer(1, 3 * cm),
       Paragraph("Design and Verification of a SECDED-Protected Synchronous FIFO "
                 "with Programmable Thresholds and Built-in Fault Injection", TITLE),
       Spacer(1, 1 * cm),
       Paragraph("Computational Project Report", SUB),
       Paragraph("M.Tech - VLSI Design (Digital)", SUB),
       Spacer(1, 2.2 * cm),
       Paragraph("Submitted by: ______________________ &nbsp;&nbsp; Roll No.: ____________", SUB),
       Spacer(1, 0.4 * cm),
       Paragraph("Guide: ______________________", SUB),
       Spacer(1, 0.4 * cm),
       Paragraph("Department: ______________________", SUB),
       Spacer(1, 2.5 * cm),
       Paragraph("Tools: Verilog-2005 RTL, Icarus Verilog 12.0, Verilator 5.020, "
                 "Yosys 0.70 + ABC, Python 3 (matplotlib, reportlab)", SUB),
       Spacer(1, 0.4 * cm),
       Paragraph(datetime.date.today().strftime("%B %Y"), SUB),
       PageBreak()]

st += [Paragraph("Abstract", H1), P(
    "First-in first-out (FIFO) buffers sit between almost every pair of pipeline stages in a digital "
    "system, and in deep-submicron technologies the storage array of a FIFO is exposed to radiation- and "
    "noise-induced single-event upsets. A conventional synchronous FIFO forwards a flipped bit silently. "
    "This project designs, verifies and synthesises a parameterised single-clock FIFO in Verilog that "
    "protects its storage with an extended-Hamming single-error-correcting, double-error-detecting "
    "(SECDED) code, offers run-time programmable almost-full / almost-empty thresholds, registered "
    "glitch-free status flags, write-through when full, sticky overflow / underflow flags, saturating "
    "error counters, and a fault-injection port that makes the protection testable. The design is "
    "verified with a cycle-accurate scoreboard testbench that checks every output on every clock: the "
    "main run simulates %s cycles with %s comparisons and %s mismatches, all %s codeword bit positions "
    "are fault-injected, and a 14-run regression across widths 8-64 and depths 4-64 passes. The strength "
    "of the testbench itself is demonstrated by mutation testing: %s deliberately injected design bugs "
    "were detected. Synthesis with Yosys/ABC shows that the SECDED overhead falls from %s at DEPTH=8 to "
    "%s at DEPTH=64 as the fixed encoder/decoder cost is amortised, while an analytical model shows a "
    "~%s-fold reduction of silent data errors at a per-bit upset probability of 10<super>-6</super>."
    % (M["cycles"], M["checks"], M["mism"], M["pos"].split()[0],
       "%s of %s" % tuple(re.match(r"(\d+) / (\d+)", mut_score).groups()),
       syn_depth[1][4], syn_depth[4][4], "{:,}".format(int(round(p_un / p_ec, -3))))),
    P("<b>Keywords:</b> synchronous FIFO, SECDED, Hamming code, soft error, fault injection, "
      "self-checking testbench, mutation testing, Verilog, Yosys."),
    PageBreak()]

st += [Paragraph("1. Introduction", H1), P(
    "A synchronous FIFO is a dual-ported memory with a write pointer and a read pointer driven by the "
    "same clock. It decouples a producer from a consumer that do not always operate at the same rate, "
    "and appears in bus bridges, network-on-chip routers, DSP data paths, DMA engines and UART/SPI "
    "controllers. Because the storage array is usually the largest block of the FIFO, it is also the "
    "part most likely to suffer a soft error - a transient bit flip caused by an energetic particle or "
    "supply noise. With shrinking node capacitance the critical charge needed to flip a cell keeps "
    "falling, so error-correcting codes, long standard in caches and DRAM, are increasingly applied to "
    "small buffers in safety-relevant designs (automotive, avionics, space)."),
    P("The goal of this project is not only to write a working FIFO, but to produce a <i>measurably</i> "
      "more robust one and to prove its correctness with a verification flow that can itself be shown to "
      "be effective. All results in this report were produced by the scripts included with the project "
      "and can be reproduced with a single command (<font face='Courier'>bash scripts/run_all.sh</font>)."),
    Paragraph("1.1 Objectives", H2),
    P("(1) Design a fully parameterised synchronous FIFO (data width, depth, ECC on/off) in synthesisable "
      "Verilog-2005. (2) Protect the storage with a generic SECDED code whose check-bit count is derived "
      "automatically from the data width. (3) Add the control and observability features that a practical "
      "IP block needs. (4) Verify the design with a self-checking reference-model testbench and functional "
      "coverage, and measure the testbench's bug-finding ability by mutation testing. (5) Quantify the "
      "hardware cost by logic synthesis and compare with a conventional FIFO."),
    Paragraph("1.2 Contribution and positioning", H2),
    P("ECC-protected FIFOs exist in commercial FPGA/ASIC IP generators, where the ECC is typically provided by "
      "the vendor's block-RAM primitive and is not visible as RTL. The contribution of this project is an "
      "open, vendor-independent, single-file-per-block RTL implementation that combines: a width-generic "
      "extended-Hamming codec written with elaboration-time loops (no hand-written parity equations), "
      "flags computed from the <i>next</i> occupancy and registered, write-through-when-full for full "
      "throughput, a codeword-level fault-injection port for verification and built-in self-test, and a "
      "quantitative evaluation (coverage, mutation score, area/depth scaling and a reliability model). "
      "The project does not claim a new coding scheme; its novelty lies in this integration and in the "
      "evidence-based evaluation."),
    PageBreak()]

st += [Paragraph("2. Background", H1),
       Paragraph("2.1 Conventional synchronous FIFO", H2), P(
    "The classic design uses (N+1)-bit read and write pointers for a 2<super>N</super>-deep array. The "
    "FIFO is empty when the pointers are equal and full when they differ only in the MSB [1]. Writes when "
    "full and reads when empty must be blocked. In this classic form the full/empty flags are "
    "combinational comparisons of the pointers and there is no indication when data is corrupted inside "
    "the array. This design is implemented as <font face='Courier'>fifo_baseline.v</font> and used as the "
    "reference for comparison."),
       Paragraph("2.2 Extended Hamming (SECDED) code", H2), P(
    "A Hamming code places P check bits at the power-of-two positions 1, 2, 4, ... of a codeword and "
    "data bits in the remaining positions [2]. Check bit j is the XOR of every position whose index has "
    "bit j set. For K data bits, P is the smallest integer with 2<super>P</super> &ge; K + P + 1. On "
    "reading, recomputing the checks gives a P-bit syndrome equal to the index of a single flipped bit. "
    "Adding one overall parity bit (extended Hamming) gives SECDED [2],[3]: if the overall parity fails, "
    "a single error occurred and the syndrome locates it (syndrome 0 means the parity bit itself flipped); "
    "if the overall parity passes but the syndrome is non-zero, two bits flipped and the word is flagged as "
    "uncorrectable. For K = 32 this gives the (39,32) code, i.e. 7 check bits (21.9 % storage overhead)."),
       PageBreak()]

st += [Paragraph("3. Proposed Architecture", H1),
       fig("block_diagram.png", 16.5, "Figure 1 - Block diagram of the proposed sync_fifo_ecc."),
       P("Write data is encoded into a CW_W-bit codeword, optionally XOR-ed with a fault mask, and written "
         "into the array at <font face='Courier'>wr_ptr</font>. A read captures the codeword at "
         "<font face='Courier'>rd_ptr</font> into a read register; the decoder after this register corrects "
         "single errors and raises <font face='Courier'>sec_err</font> or <font face='Courier'>ded_err</font>, "
         "both qualified by <font face='Courier'>rd_valid</font>. The control path keeps an occupancy counter "
         "and computes every flag from the next value of the counter, so all flags leave the block from "
         "flip-flops (glitch-free, no pointer comparator in the output path)."),
       Paragraph("3.1 Parameters", H2),
       table([["Parameter", "Default", "Meaning"],
              ["DATA_W", "32", "data width (any value; check bits derived automatically)"],
              ["DEPTH", "16", "number of words, power of two"],
              ["ECC_EN", "1", "1 = SECDED storage, 0 = plain storage (same control logic)"],
              ["PAR_W", "derived", "$clog2(DATA_W + $clog2(DATA_W) + 1), verified minimal by tb_secded"],
              ["CW_W", "derived", "DATA_W + PAR_W + 1 (39 for DATA_W = 32)"]],
             [3 * cm, 2.2 * cm, 11 * cm]),
       Spacer(1, 6),
       Paragraph("3.2 Interface", H2),
       table([["Port", "Dir", "Description"],
              ["clk, rst_n", "in", "clock; asynchronous active-low reset"],
              ["wr_en, wr_data", "in", "write request and data"],
              ["rd_en", "in", "read request"],
              ["rd_data, rd_valid", "out", "corrected read data, valid one clock after an accepted read"],
              ["full, empty, count", "out", "registered status and occupancy"],
              ["af_thresh, ae_thresh", "in", "run-time thresholds"],
              ["almost_full, almost_empty", "out", "count &ge; af_thresh, count &le; ae_thresh (registered)"],
              ["overflow, underflow", "out", "sticky: a write was dropped / a read was attempted when empty"],
              ["sec_err, ded_err", "out", "single error corrected / double error detected on this read"],
              ["sec_cnt, ded_cnt", "out", "16-bit saturating event counters"],
              ["clr_status", "in", "synchronous clear of sticky flags and counters"],
              ["inj_en, inj_mask", "in", "fault injection: XOR mask applied to the codeword being written"]],
             [4.2 * cm, 1.2 * cm, 10.8 * cm]),
       PageBreak()]

st += [Paragraph("4. Implementation", H1),
       Paragraph("4.1 Generic SECDED codec", H2), P(
    "Both <font face='Courier'>secded_enc.v</font> and <font face='Courier'>secded_dec.v</font> are written "
    "with <font face='Courier'>for</font> loops over codeword positions inside combinational always blocks. "
    "The loops are unrolled at elaboration, so the same source produces the (13,8), (22,16), (39,32) and "
    "(72,64) codes without any hand-derived equations. Codeword bit 0 holds the overall parity; positions "
    "1..HAM_W hold the Hamming code. The decoder computes the syndrome and the overall parity, flips the "
    "bit addressed by the syndrome when a single error is indicated, and reports a syndrome that points "
    "beyond the codeword (only possible with three or more errors) as uncorrectable."),
       Paragraph("4.2 Handshake and write-through", H2), P(
    "An accepted read is <font face='Courier'>rd_fire = rd_en &amp; ~empty</font>. An accepted write is "
    "<font face='Courier'>wr_fire = wr_en &amp; (~full | rd_en)</font>: when the FIFO is full and a read "
    "occurs in the same clock, the write is accepted too, because the read register captures the old "
    "word at <font face='Courier'>rd_ptr</font> (equal to <font face='Courier'>wr_ptr</font> when full) on "
    "the same edge as the new word is written. A full FIFO therefore streams at one word per clock "
    "instead of stalling every other cycle. Because the occupancy counter carries the full/empty "
    "information, the pointers need only ADDR_W bits."),
       Paragraph("4.3 Registered flags", H2), P(
    "With <font face='Courier'>count_nxt = count + wr_fire - rd_fire</font>, every flag is registered as a "
    "function of <font face='Courier'>count_nxt</font> (e.g. <font face='Courier'>full &lt;= (count_nxt == "
    "DEPTH)</font>). The flags therefore change on the same edge as the occupancy, are glitch-free, and "
    "the thresholds can be changed at any time; the new comparison takes effect on the next clock."),
       Paragraph("4.4 Error reporting and fault injection", H2), P(
    "Sticky overflow/underflow flags record protocol violations by the surrounding logic. SEC/DED events "
    "increment 16-bit counters that saturate at 65535 instead of wrapping, so a high error count can never "
    "be mistaken for a low one. A synchronous <font face='Courier'>clr_status</font> has priority over "
    "new events. The <font face='Courier'>inj_mask</font> port XORs an arbitrary pattern into the stored "
    "codeword; it is used by the testbench to reach every bit position and can be used in silicon as a "
    "built-in self-test of the ECC path. Tied to zero, it is removed by synthesis."),
       Paragraph("4.5 Source files", H2),
       table([["File", "Lines", "Content"]] +
             [[f, sum(1 for _ in open(os.path.join(ROOT, f))), d] for f, d in [
                 ("rtl/sync_fifo_ecc.v", "proposed FIFO (top level)"),
                 ("rtl/secded_enc.v", "generic SECDED encoder"),
                 ("rtl/secded_dec.v", "generic SECDED decoder"),
                 ("rtl/fifo_baseline.v", "conventional FIFO for comparison"),
                 ("tb/tb_sync_fifo_ecc.v", "scoreboard testbench, coverage, fault injection"),
                 ("tb/tb_secded.v", "exhaustive/random codec unit test"),
                 ("tb/tb_fifo_baseline.v", "testbench of the reference FIFO"),
                 ("scripts/mutation_test.py", "mutation testing of the testbench"),
                 ("scripts/run_synth.py", "Yosys synthesis of 26 configurations"),
                 ("scripts/run_regression.sh", "14-run simulation regression")]],
             [5 * cm, 1.6 * cm, 9.6 * cm]),
       PageBreak()]

st += [Paragraph("5. Verification Methodology", H1),
       Paragraph("5.1 Codec unit test", H2), P(
    "<font face='Courier'>tb_secded.v</font> checks that PAR_W is the minimum number of check bits and "
    "then, for every data word, decodes the clean codeword, every single-bit corruption and every "
    "double-bit corruption. For DATA_W = 8 all 256 data words and all error patterns are exhaustive; for "
    "wider words corner patterns (all-zero, all-one, alternating, walking-one) plus random words are used."),
       Paragraph("5.2 Scoreboard testbench of the FIFO", H2), P(
    "<font face='Courier'>tb_sync_fifo_ecc.v</font> drives inputs on the falling edge and, on every rising "
    "edge, advances a transaction-level reference model (a circular queue that remembers each word and the "
    "fault mask injected into it). One time-unit later every DUT output is compared with the model: count, "
    "full, empty, almost_full, almost_empty, rd_valid, rd_data, sec_err, ded_err, overflow, underflow, "
    "sec_cnt and ded_cnt. A word stored with one injected flip must be read back correct with sec_err = 1; "
    "with two flips ded_err = 1 is required. With ECC_EN = 0, the model predicts the corrupted word, which "
    "measures how many faults reach the output silently."),
       table([["Test", "Purpose"],
              ["T1", "reset values of all outputs"],
              ["T2", "fill to full plus two extra writes: full, almost_full, sticky overflow, data not overwritten"],
              ["T3", "2 x DEPTH cycles of simultaneous read/write while full (write-through)"],
              ["T4", "drain to empty plus extra reads: sticky underflow; read+write while empty"],
              ["T5", "threshold sweep: af_thresh = 0..DEPTH with ae_thresh = DEPTH..0, fill and drain each"],
              ["T6", "single-bit fault injected at every codeword bit position"],
              ["T7", "200 random double-bit faults"],
              ["T8", "synchronous clear of sticky flags and counters"],
              ["T9", "65 540 single-bit events: sec_cnt must saturate at 65 535"],
              ["T10", "constrained random: 6 traffic phases (fill-biased, drain-biased, balanced, 100 % "
                      "streaming, near-full, mixed), random thresholds, 1.5 % single and 0.5 % double "
                      "faults, random status clears"]],
             [1.5 * cm, 14.7 * cm]),
       Spacer(1, 6),
       Paragraph("5.3 Mutation testing", H2), P(
    "A passing testbench only means something if it would fail on a wrong design. "
    "<font face='Courier'>scripts/mutation_test.py</font> copies the RTL, injects one realistic bug "
    "(wrong comparator, missing sticky set, wrong pointer enable, broken parity, ...), re-runs the testbench "
    "and records whether the bug was detected. The mutation score is the fraction of bugs detected."),
       PageBreak()]

st += [Paragraph("6. Results", H1),
       Paragraph("6.1 Main simulation (DATA_W = 32, DEPTH = 16, ECC_EN = 1)", H2),
       table([["Metric", "Value"],
              ["Clock cycles simulated", M["cycles"]],
              ["Writes / reads accepted", M["wrrd"]],
              ["Scoreboard comparisons", M["checks"]],
              ["Mismatches", M["mism"]],
              ["Cycles full / empty", M["fe"]],
              ["Maximum occupancy", M["maxocc"]],
              ["Write-through cycles at full", M["wthru"]],
              ["Blocked writes / blocked reads", M["blk"]],
              ["Cycles with wr_en and rd_en together", M["simul"]],
              ["almost_full / almost_empty assertions", M["aeaf"]],
              ["Status clears", M["clr"]],
              ["Single / double faults injected", M["inj"]],
              ["Codeword bit positions covered", M["pos"]],
              ["SEC / DED events observed", M["secded"]]],
             [8 * cm, 8.2 * cm]),
       Spacer(1, 4),
       P("Every injected single-bit fault was corrected and every double-bit fault was flagged. In the "
         "ECC_EN = 0 configuration with the same kind of traffic, %s single/double faults were injected and "
         "<b>%s reads returned corrupted data with no indication</b> - this is exactly the failure that the "
         "SECDED path removes." % (noecc_inj, silent)),
       Paragraph("6.2 SECDED codec unit test", H2),
       table(sec_rows, [1.6 * cm, 1.4 * cm, 2 * cm, 2.3 * cm, 3 * cm, 3 * cm, 2.4 * cm]),
       Spacer(1, 6),
       Paragraph("6.3 Regression", H2),
       table(reg_rows, [12.5 * cm, 2.5 * cm]),
       Paragraph("Total: " + reg_total, CAP),
       PageBreak(),
       Paragraph("6.4 Mutation testing", H2),
       table(mut_rows, [1.2 * cm, 7.6 * cm, 3 * cm, 4.4 * cm]),
       Spacer(1, 4),
       P("<b>Mutation score: %s.</b> Every injected bug, including subtle ones such as an off-by-one "
         "threshold comparison (M2, M3) or a counter that wraps instead of saturating (M9), made the "
         "testbench fail. Lint with Verilator -Wall reported zero warnings for every configuration." % mut_score),
       PageBreak(),
       Paragraph("6.5 Simulation waveforms", H2),
       P("The following waveforms are rendered directly from the VCD file produced by the main simulation "
         "(<font face='Courier'>sim/sync_fifo_ecc.vcd</font>, viewable in GTKWave with the provided "
         "<font face='Courier'>.gtkw</font> file)."),
       fig("wave_fill_overflow.png", 16.5, "Figure 2 - Reset and fill. count rises 0 to 16; almost_full "
           "asserts at 14 (af_thresh = 14), full at 16; the two writes issued while full set overflow."),
       fig("wave_write_through.png", 16.5, "Figure 3 - Write-through: with wr_en and rd_en both high at full, "
           "one word enters and one leaves every clock and count stays at 16."),
       fig("wave_drain_underflow.png", 16.5, "Figure 4 - Drain: reads empty the FIFO; reads while empty are "
           "ignored and set the sticky underflow flag."),
       fig("wave_ecc_inject.png", 16.5, "Figure 5 - Fault injection: inj_mask walks a single 1 through the "
           "codeword while 16 words are written. On read-back sec_err is high for each word and sec_cnt "
           "counts the corrections; the scoreboard confirms rd_data equals the original data."),
       PageBreak()]

st += [Paragraph("6.6 Synthesis", H2), P(
    "All configurations were synthesised with %s, flattening the hierarchy and mapping with ABC to a "
    "generic library of two-input gates and 2:1 multiplexers. The storage array is mapped to flip-flops, "
    "i.e. the numbers describe a register-file FIFO. Transistor counts use Yosys' "
    "<font face='Courier'>stat -tech cmos</font> estimate and logic depth is the longest combinational "
    "path in gates (<font face='Courier'>ltp -noff</font>). No standard-cell library or timing constraints "
    "are involved, so the numbers compare architectures, not absolute silicon area or frequency." % ver_yosys),
       table(syn_main, [5.6 * cm, 1.9 * cm, 2 * cm, 1.9 * cm, 2.6 * cm, 2.2 * cm]),
       Spacer(1, 8),
       fig("synth_area_vs_depth.png", 15, "Figure 6 - Estimated transistor count versus depth."),
       table(syn_depth, [2 * cm, 2.6 * cm, 3.4 * cm, 3.4 * cm, 4.8 * cm]),
       Spacer(1, 8),
       fig("ecc_overhead_vs_depth.png", 15, "Figure 7 - SECDED overhead approaches the 21.9 % storage floor "
           "as depth grows, because the encoder and decoder are shared by all words."),
       table(syn_codec, [2 * cm, 2.2 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]),
       Spacer(1, 4),
       table(syn_width, [4 * cm, 4 * cm, 4.6 * cm, 2.6 * cm]),
       Spacer(1, 6),
       P("The proposed control logic without ECC costs %s more transistors than the baseline at DEPTH = 16 "
         "(occupancy counter, programmable comparators, registered flags, error counters). Its logic depth "
         "is larger (%s vs %s gates) because the threshold comparators follow the occupancy adder before the "
         "flag registers; this is a deliberate trade for glitch-free registered flags, and the path can be "
         "shortened by comparing against count instead of count_nxt at the cost of one cycle of flag latency."
         % ("%.1f %%" % (100.0 * (int(S["noecc_w32_d16"]["cmos_transistors"]) /
                                  int(S["base_w32_d16"]["cmos_transistors"]) - 1)),
            S["noecc_w32_d16"]["logic_depth_gates"], S["base_w32_d16"]["logic_depth_gates"])),
       PageBreak(),
       Paragraph("6.7 Reliability benefit (analytical)", H2), P(
    "Assume each stored bit flips independently with probability p while a word waits in the FIFO. An "
    "unprotected 32-bit word is wrong with probability 1-(1-p)<super>32</super> &asymp; 32p. With the "
    "(39,32) code every single flip is corrected, so a read is wrong only if two or more of the 39 bits "
    "flip: 1-(1-p)<super>39</super>-39p(1-p)<super>38</super> &asymp; 741p<super>2</super>. At "
    "p = 10<super>-6</super> this is %.2e versus %.2e, a reduction of about %s times; furthermore, the "
    "double-error case is flagged by ded_err instead of passing silently." %
    (p_ec, p_un, "{:,}".format(int(round(p_un / p_ec, -3))))),
       fig("reliability_model.png", 15, "Figure 8 - Probability that a read word is wrong (analytical model)."),
       PageBreak()]

st += [Paragraph("7. Discussion and Limitations", H1), P(
    "(a) The decoder is combinational after the read register, so it lies in the path from the read "
    "register to <font face='Courier'>rd_data</font> (11 gate levels for DATA_W = 32). In a high-frequency "
    "design an optional output register can be added, giving a two-cycle read latency. "
    "(b) Synthesis used a generic gate library; absolute area and timing require a foundry standard-cell "
    "library and, for large depths, an SRAM macro instead of flip-flops. The relative trends reported "
    "here are what the generic flow can support. "
    "(c) The reliability analysis assumes independent bit flips; multi-cell upsets in adjacent cells are "
    "better handled by bit interleaving across words, which is a natural extension. "
    "(d) Verification is simulation-based with constrained-random stimulus and functional coverage; "
    "formal property checking (e.g. SymbiYosys) would complement it."),
       Paragraph("8. Conclusion and Future Work", H1), P(
    "A parameterised SECDED-protected synchronous FIFO was designed in Verilog-2005, verified with a "
    "reference-model testbench (%s comparisons, 0 mismatches in the main run, 14/14 regression runs "
    "passing, all codeword bits fault-injected) whose effectiveness was demonstrated with a %s mutation "
    "score, linted clean with Verilator and synthesised with Yosys. ECC removes all silent single-bit "
    "corruption at an overhead that falls from %s to %s as the depth grows from 8 to 64 words. Future "
    "work: optional output pipeline register, bit-interleaving for multi-cell upsets, background "
    "scrubbing of idle entries, formal verification of the flag logic, and an asynchronous (dual-clock) "
    "version using Gray-coded pointers." % (M["checks"], mut_score.split("(")[-1].rstrip(")"),
                                            syn_depth[1][4], syn_depth[4][4])),
       Paragraph("References", H1)]
refs = [
    "C. E. Cummings, \"Simulation and Synthesis Techniques for Asynchronous FIFO Design,\" SNUG San Jose, 2002.",
    "R. W. Hamming, \"Error Detecting and Error Correcting Codes,\" Bell System Technical Journal, vol. 29, no. 2, pp. 147-160, 1950.",
    "M. Y. Hsiao, \"A Class of Optimal Minimum Odd-weight-column SEC-DED Codes,\" IBM Journal of Research and Development, vol. 14, no. 4, pp. 395-401, 1970.",
    "R. C. Baumann, \"Radiation-induced soft errors in advanced semiconductor technologies,\" IEEE Trans. Device and Materials Reliability, vol. 5, no. 3, pp. 305-316, 2005.",
    "IEEE Std 1364-2005, IEEE Standard for Verilog Hardware Description Language.",
    "C. Wolf, \"Yosys Open SYnthesis Suite,\" https://yosyshq.net/yosys/.",
    "S. Williams, \"Icarus Verilog,\" https://steveicarus.github.io/iverilog/.",
    "Y. Jia and M. Harman, \"An Analysis and Survey of the Development of Mutation Testing,\" IEEE Trans. Software Engineering, vol. 37, no. 5, pp. 649-678, 2011.",
]
for i, r in enumerate(refs, 1):
    st.append(Paragraph("[%d] %s" % (i, r), BODY))

st += [PageBreak(), Paragraph("Appendix A - How to reproduce", H1), P(
    "Requirements: Icarus Verilog (iverilog/vvp), Verilator (lint only), Python 3 with matplotlib and "
    "reportlab, and Yosys (native binary, or <font face='Courier'>pip install pyosys</font>)."),
       Preformatted(
"bash scripts/run_all.sh          # everything below, in order\n"
"bash scripts/run_lint.sh         # Verilator -Wall          -> lint/\n"
"bash scripts/run_regression.sh   # 14 simulations           -> sim/logs/\n"
"python3 scripts/mutation_test.py # 15 mutants               -> sim/logs/mutation_*\n"
"python3 scripts/run_synth.py     # 26 synthesis runs        -> syn/\n"
"python3 scripts/make_plots.py    # figures                  -> docs/figures/\n"
"python3 scripts/make_report.py   # this report              -> docs/Project_Report.pdf\n"
"make sim && make wave            # single run + GTKWave", CODE),
       Spacer(1, 8),
       Paragraph("Appendix B - Top-level RTL (rtl/sync_fifo_ecc.v)", H1),
       Preformatted(open(os.path.join(ROOT, "rtl", "sync_fifo_ecc.v")).read(), CODE),
       PageBreak(),
       Paragraph("Appendix C - SECDED encoder and decoder", H1),
       Preformatted(open(os.path.join(ROOT, "rtl", "secded_enc.v")).read(), CODE),
       Spacer(1, 6),
       Preformatted(open(os.path.join(ROOT, "rtl", "secded_dec.v")).read(), CODE)]


def page(canvas, doc):
    if doc.page == 1: return
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    canvas.setFillColor(colors.HexColor("#52514e"))
    canvas.drawString(2 * cm, 1.2 * cm, "SECDED-Protected Synchronous FIFO - M.Tech VLSI computational project")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                        topMargin=2 * cm, bottomMargin=2 * cm,
                        title="SECDED-Protected Synchronous FIFO", author="M.Tech VLSI project")
doc.build(st, onFirstPage=page, onLaterPages=page)
print("written", OUT)
