#!/usr/bin/env bash
#------------------------------------------------------------------------------
# run_all.sh - reproduces every result in the project from a clean checkout
#   1. lint (Verilator)   2. simulation regression (Icarus Verilog)
#   3. mutation testing   4. synthesis (Yosys)   5. figures   6. report
#------------------------------------------------------------------------------
set -e
cd "$(dirname "$0")/.."
echo "### 1/6 lint";        bash scripts/run_lint.sh
echo "### 2/6 regression";  bash scripts/run_regression.sh
echo "### 3/6 mutation";    python3 scripts/mutation_test.py
echo "### 4/6 synthesis";   python3 scripts/run_synth.py
echo "### 5/6 figures";     python3 scripts/make_plots.py
echo "### 6/6 report";      python3 scripts/make_report.py
echo "### gate level";      python3 scripts/gate_level.py && bash scripts/run_gate_level_sim.sh
echo "All steps finished."
