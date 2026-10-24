#!/usr/bin/env bash
# run_lint.sh - Verilator -Wall lint of all RTL (empty log = clean)
cd "$(dirname "$0")/.."
mkdir -p lint
R="rtl/sync_fifo_ecc.v rtl/secded_enc.v rtl/secded_dec.v"
verilator --lint-only -Wall --top-module sync_fifo_ecc $R            > lint/verilator_sync_fifo_ecc.log   2>&1
verilator --lint-only -Wall --top-module sync_fifo_ecc -GECC_EN=0 $R > lint/verilator_sync_fifo_noecc.log 2>&1
verilator --lint-only -Wall --top-module sync_fifo_ecc -GDATA_W=64 -GDEPTH=64 $R > lint/verilator_sync_fifo_w64.log 2>&1
verilator --lint-only -Wall rtl/fifo_baseline.v                      > lint/verilator_fifo_baseline.log   2>&1
for f in lint/*.log; do
    if [ -s "$f" ]; then echo "$f : WARNINGS"; cat "$f"; else echo "$f : clean (0 warnings)"; fi
done
