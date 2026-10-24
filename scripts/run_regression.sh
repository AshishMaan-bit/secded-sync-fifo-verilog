#!/usr/bin/env bash
#------------------------------------------------------------------------------
# run_regression.sh - full simulation regression with Icarus Verilog
#   Run from the project root:  bash scripts/run_regression.sh
#   Logs  -> sim/logs/*.log      Summary -> sim/logs/regression_summary.txt
#   VCD   -> sim/sync_fifo_ecc.vcd (main configuration only)
#------------------------------------------------------------------------------
set -u
cd "$(dirname "$0")/.."
mkdir -p sim/logs build
RTL="rtl/sync_fifo_ecc.v rtl/secded_enc.v rtl/secded_dec.v"
SUM=sim/logs/regression_summary.txt
: > "$SUM"
pass=0; fail=0

record () {   # $1 = name, $2 = log file
    if grep -q "RESULT: PASS" "$2"; then r=PASS; pass=$((pass+1)); else r=FAIL; fail=$((fail+1)); fi
    printf "%-46s %s\n" "$1" "$r" | tee -a "$SUM"
}

echo "== SECDED codec unit tests ==" | tee -a "$SUM"
for w in 8 16 32 64; do
    iverilog -g2005 -Wall -P tb_secded.DATA_W=$w -o build/secded_$w.vvp \
        tb/tb_secded.v rtl/secded_enc.v rtl/secded_dec.v || exit 1
    vvp -n build/secded_$w.vvp > sim/logs/secded_w$w.log
    record "secded DATA_W=$w" sim/logs/secded_w$w.log
done

echo "== Baseline FIFO ==" | tee -a "$SUM"
iverilog -g2005 -Wall -o build/base.vvp tb/tb_fifo_baseline.v rtl/fifo_baseline.v || exit 1
vvp -n build/base.vvp > sim/logs/fifo_baseline.log
record "fifo_baseline W32 D16" sim/logs/fifo_baseline.log

echo "== SECDED FIFO configurations ==" | tee -a "$SUM"
run_fifo () {  # name  W  D  ECC  NRAND  plusargs...
    local name=$1 w=$2 d=$3 e=$4 n=$5; shift 5
    iverilog -g2005 -Wall -P tb_sync_fifo_ecc.DATA_W=$w -P tb_sync_fifo_ecc.DEPTH=$d \
        -P tb_sync_fifo_ecc.ECC_EN=$e -P tb_sync_fifo_ecc.N_RAND=$n \
        -o build/$name.vvp tb/tb_sync_fifo_ecc.v $RTL || exit 1
    (cd sim && vvp -n ../build/$name.vvp "$@" > logs/$name.log)
    record "$name (W=$w D=$d ECC=$e $*)" sim/logs/$name.log
}
run_fifo fifo_main_w32_d16_ecc   32 16 1 50000 +vcd +sat
run_fifo fifo_w8_d4_ecc           8  4 1 20000 +seed=11
run_fifo fifo_w16_d8_ecc         16  8 1 20000 +seed=22
run_fifo fifo_w64_d64_ecc        64 64 1 20000 +seed=33
run_fifo fifo_w32_d16_noecc      32 16 0 20000 +seed=44
for s in 101 202 303 404; do
    run_fifo fifo_w32_d16_seed$s 32 16 1 20000 +seed=$s
done

echo "------------------------------------------------" | tee -a "$SUM"
echo "TOTAL: $pass passed, $fail failed" | tee -a "$SUM"
[ $fail -eq 0 ]
