//-----------------------------------------------------------------------------
// File        : tb_fifo_baseline.v
// Description : Self-checking testbench for the conventional reference FIFO
//               (fill, overflow attempt, drain, underflow attempt, random).
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_fifo_baseline;
    parameter integer DATA_W = 32;
    parameter integer DEPTH  = 16;
    parameter integer N_RAND = 20000;

    reg               clk = 0, rst_n = 0, wr_en = 0, rd_en = 0;
    reg  [DATA_W-1:0] wr_data = 0;
    wire [DATA_W-1:0] rd_data;
    wire              rd_valid, full, empty;

    always #5 clk = ~clk;

    fifo_baseline #(.DATA_W(DATA_W), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_data(wr_data),
        .rd_en(rd_en), .rd_data(rd_data), .rd_valid(rd_valid),
        .full(full), .empty(empty));

    reg [DATA_W-1:0] q [0:DEPTH-1];
    integer head, tail, cnt, n_err, n_chk, k, seed;
    reg mv, wf, rf;
    reg [DATA_W-1:0] exp;

    task cycle(input w, input [DATA_W-1:0] d, input r);
        begin
            @(negedge clk); wr_en = w; wr_data = d; rd_en = r;
            @(posedge clk);
            rf = r & (cnt != 0);
            wf = w & (cnt != DEPTH);
            if (rf) begin exp = q[head]; head = (head + 1) % DEPTH; end
            if (wf) begin q[tail] = d; tail = (tail + 1) % DEPTH; end
            cnt = cnt + wf - rf; mv = rf;
            #1;
            n_chk = n_chk + 3;
            if (full !== (cnt == DEPTH)) n_err = n_err + 1;
            if (empty !== (cnt == 0))    n_err = n_err + 1;
            if (rd_valid !== mv)         n_err = n_err + 1;
            if (mv) begin
                n_chk = n_chk + 1;
                if (rd_data !== exp) n_err = n_err + 1;
            end
        end
    endtask

    initial begin
        seed = 7; head = 0; tail = 0; cnt = 0; n_err = 0; n_chk = 0; mv = 0;
        #23 rst_n = 1;
        for (k = 0; k < DEPTH + 2; k = k + 1) cycle(1, {$random(seed)}, 0);
        for (k = 0; k < DEPTH + 2; k = k + 1) cycle(0, 0, 1);
        for (k = 0; k < N_RAND; k = k + 1)
            cycle(({$random(seed)} % 100) < 55, {$random(seed), $random(seed)},
                  ({$random(seed)} % 100) < 50);
        $display(" tb_fifo_baseline DATA_W=%0d DEPTH=%0d : %0d checks, %0d mismatches",
                 DATA_W, DEPTH, n_chk, n_err);
        if (n_err == 0) $display(" RESULT: PASS"); else $display(" RESULT: FAIL");
        $finish;
    end
endmodule
