#!/usr/bin/env bash
#------------------------------------------------------------------------------
# run_gate_level_sim.sh - re-runs the ORIGINAL self-checking testbenches on the
# synthesised gate-level netlists, with every gate simulated as NMOS/PMOS
# switches (gate_level/cmos_cells.v). A PASS proves that the transistor-level
# circuit behaves exactly like the RTL.
#   Run from the project root after:  python3 scripts/gate_level.py
#------------------------------------------------------------------------------
set -u
cd "$(dirname "$0")/.."
mkdir -p build gate_level/logs
G=gate_level; L=gate_level/logs; S=$L/gate_level_summary.txt
: > $S; pass=0; fail=0
rec () { if grep -q "RESULT: PASS" "$2"; then r=PASS; pass=$((pass+1)); else r=FAIL; fail=$((fail+1)); fi
         printf "%-58s %s\n" "$1" "$r" | tee -a $S; }

for w in 8 32; do
  iverilog -g2005 -P tb_secded.DATA_W=$w -o build/gl_sec$w.vvp tb/tb_secded.v \
      $G/netlist_enc_w$w.v $G/netlist_dec_w$w.v $G/cmos_cells.v || exit 1
  vvp -n build/gl_sec$w.vvp > $L/gl_secded_w$w.log
  rec "SECDED codec DATA_W=$w  (transistor level)" $L/gl_secded_w$w.log
done

iverilog -g2005 -P tb_fifo_baseline.DATA_W=8 -P tb_fifo_baseline.DEPTH=4 -o build/gl_base.vvp \
    tb/tb_fifo_baseline.v $G/netlist_base_w8_d4.v $G/cmos_cells.v || exit 1
vvp -n build/gl_base.vvp > $L/gl_fifo_baseline_w8_d4.log
rec "baseline FIFO W=8 D=4  (transistor level)" $L/gl_fifo_baseline_w8_d4.log

iverilog -g2005 -P tb_sync_fifo_ecc.DATA_W=8 -P tb_sync_fifo_ecc.DEPTH=4 -P tb_sync_fifo_ecc.N_RAND=20000 \
    -o build/gl_fifo8.vvp tb/tb_sync_fifo_ecc.v $G/netlist_fifo_w8_d4.v $G/cmos_cells.v || exit 1
vvp -n build/gl_fifo8.vvp +sat +seed=7 > $L/gl_fifo_w8_d4.log
rec "SECDED FIFO W=8 D=4 +sat (transistor level)" $L/gl_fifo_w8_d4.log

iverilog -g2005 -P tb_sync_fifo_ecc.DATA_W=32 -P tb_sync_fifo_ecc.DEPTH=16 -P tb_sync_fifo_ecc.N_RAND=6000 \
    -o build/gl_fifo32.vvp tb/tb_sync_fifo_ecc.v $G/netlist_fifo_w32_d16.v $G/cmos_cells.v || exit 1
vvp -n build/gl_fifo32.vvp +seed=99 > $L/gl_fifo_w32_d16.log
rec "SECDED FIFO W=32 D=16 (transistor level, 47k transistors)" $L/gl_fifo_w32_d16.log

# negative control: a deliberately broken NAND2 (pull-down NMOS in parallel
# instead of series) must make the simulation FAIL
sed 's/nmos mna (y, x,   A);          \/\/ pull-down network: 2 NMOS in SERIES/nmos mna (y, gnd, A);/' \
    $G/cmos_cells.v > build/cmos_cells_broken.v
iverilog -g2005 -P tb_sync_fifo_ecc.DATA_W=8 -P tb_sync_fifo_ecc.DEPTH=4 -P tb_sync_fifo_ecc.N_RAND=600 \
    -o build/gl_broken.vvp tb/tb_sync_fifo_ecc.v $G/netlist_fifo_w8_d4.v build/cmos_cells_broken.v || exit 1
vvp -n build/gl_broken.vvp > $L/gl_negative_control.log
if grep -q "RESULT: FAIL" $L/gl_negative_control.log; then
    printf "%-58s %s\n" "negative control: broken NAND2 cell is detected" "PASS" | tee -a $S; pass=$((pass+1))
else
    printf "%-58s %s\n" "negative control: broken NAND2 cell is detected" "FAIL" | tee -a $S; fail=$((fail+1))
fi
echo "TOTAL: $pass passed, $fail failed" | tee -a $S
