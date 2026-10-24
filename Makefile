# Makefile - SECDED-protected synchronous FIFO
#   make sim      : main self-checking simulation (+ VCD)   -> sim/
#   make wave     : open the VCD in GTKWave
#   make regress  : full regression (14 runs)
#   make lint     : Verilator lint
#   make mutate   : mutation testing of the testbench
#   make synth    : Yosys synthesis of all configurations
#   make plots    : figures for the report
#   make report   : PDF report
#   make gates    : gate-level netlists + transistor-level simulation
#   make all      : everything (same as scripts/run_all.sh)
#   make clean

RTL = rtl/sync_fifo_ecc.v rtl/secded_enc.v rtl/secded_dec.v

.PHONY: sim wave regress lint mutate synth plots report gates all clean

sim:
	mkdir -p build sim
	iverilog -g2005 -Wall -o build/fifo.vvp tb/tb_sync_fifo_ecc.v $(RTL)
	cd sim && vvp -n ../build/fifo.vvp +vcd

wave: sim
	gtkwave sim/sync_fifo_ecc.vcd sim/sync_fifo_ecc.gtkw &

regress:
	bash scripts/run_regression.sh

lint:
	bash scripts/run_lint.sh

mutate:
	python3 scripts/mutation_test.py

synth:
	python3 scripts/run_synth.py

plots:
	python3 scripts/make_plots.py

report:
	python3 scripts/make_report.py

all:
	bash scripts/run_all.sh

clean:
	rm -rf build sim/*.vcd

gates:
	python3 scripts/gate_level.py
	bash scripts/run_gate_level_sim.sh
