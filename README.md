# SECDED-Protected Synchronous FIFO (Verilog)

M.Tech VLSI (Digital) computational project: a parameterised single-clock FIFO whose
storage is protected by an extended-Hamming SECDED code, with programmable
almost-full/almost-empty thresholds, registered flags, write-through when full,
sticky overflow/underflow flags, saturating error counters and a fault-injection port.

The full write-up is `docs/Project_Report.pdf`.

## Headline results (from the logs in this folder)

| Item | Result |
|---|---|
| Main simulation (W=32, D=16, ECC on) | 116,489 cycles, 1,486,037 scoreboard checks, **0 mismatches** |
| Regression | **14 / 14 PASS** (widths 8–64, depths 4–64, ECC on/off, 4 extra seeds) |
| SECDED unit test | all single-bit and double-bit cases correct for 8/16/32/64-bit data |
| Fault injection | all 39 codeword bits hit; 65,929 single faults corrected, 182 double faults detected |
| ECC off, same faults | 277 reads returned silently corrupted data |
| Mutation testing | **15 / 15** injected design bugs detected by the testbench |
| Lint (Verilator -Wall) | 0 warnings, all configurations |
| Synthesis (Yosys + ABC) | SECDED overhead 108.8 % at depth 8 → 32.9 % at depth 64 |

## Folder layout

```
rtl/      sync_fifo_ecc.v (top), secded_enc.v, secded_dec.v, fifo_baseline.v
tb/       tb_sync_fifo_ecc.v (scoreboard + coverage), tb_secded.v, tb_fifo_baseline.v
scripts/  run_all.sh, run_regression.sh, run_lint.sh, mutation_test.py,
          run_synth.py, make_plots.py, make_report.py
sim/      sync_fifo_ecc.vcd + .gtkw (waveform), logs/ (all simulation + mutation logs)
syn/      synth_results.csv, reports/*.rpt (full Yosys logs), tool_version.txt
lint/     Verilator logs (empty file = clean)
docs/     Project_Report.pdf, figures/
```

## Reproduce

Tools: Icarus Verilog 12, Verilator 5 (lint), Python 3 + matplotlib + reportlab,
Yosys (native binary or `pip install pyosys`).

```
bash scripts/run_all.sh      # lint, regression, mutation, synthesis, figures, report (~8 min)
make sim                     # one simulation, writes sim/sync_fifo_ecc.vcd
make wave                    # open it in GTKWave
```

Single run by hand:

```
iverilog -g2005 -o fifo.vvp tb/tb_sync_fifo_ecc.v rtl/sync_fifo_ecc.v rtl/secded_enc.v rtl/secded_dec.v
vvp fifo.vvp +vcd +seed=1234
```
Parameters can be changed with `-P tb_sync_fifo_ecc.DATA_W=16 -P tb_sync_fifo_ecc.DEPTH=8 -P tb_sync_fifo_ecc.ECC_EN=0`.

## Gate-level / transistor-level view

`gate_level/` holds the design synthesised down to only four basic static-CMOS cells
(INV, NAND2, NOR2, D flip-flop) and a cell library where every cell is written with
Verilog `nmos` / `pmos` switch primitives.

| File | What it is |
|---|---|
| `gate_level/cmos_cells.v` | INV (2T), NAND2 (4T), NOR2 (4T), NAND3 (6T), DFF/DFFR/DFFS (6×NAND3 = 36T) as NMOS/PMOS switches |
| `gate_level/netlist_*.v` | structural netlists: encoder, decoder, baseline FIFO, FIFO 8×4 and 32×16 |
| `gate_level/cell_counts.csv` | cell and transistor counts (32×16 SECDED FIFO: 47,822 transistors) |
| `gate_level/logs/` | the original testbenches re-run on the transistor-level netlists: 6/6 PASS, incl. a negative control |
| `docs/fifo_transistor_map.html` | illustrated explanation: each RTL line → gates → NMOS/PMOS |

```
python3 scripts/gate_level.py         # synthesise to INV/NAND2/NOR2/DFF
bash scripts/run_gate_level_sim.sh    # transistor-level simulations (~2 min)
```
