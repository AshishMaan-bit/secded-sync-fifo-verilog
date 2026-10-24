//-----------------------------------------------------------------------------
// File        : tb_sync_fifo_ecc.v
// Description : Self-checking, scoreboard-based testbench for sync_fifo_ecc.
//
//   A cycle-accurate transaction-level reference model runs in lock-step with
//   the DUT. Every clock the testbench compares ALL observable outputs
//   (count, full, empty, almost_full, almost_empty, rd_valid, rd_data,
//   sec_err, ded_err, overflow, underflow, sec_cnt, ded_cnt) with the model.
//
//   Directed tests
//     T1 reset state            T2 fill + overflow attempts
//     T3 write-through at full  T4 drain + underflow attempts
//     T5 threshold sweep        T6 single-bit fault at every codeword bit
//     T7 double-bit faults      T8 status clear
//     T9 SEC counter saturation (ECC_EN=1, +sat plusarg)
//   Constrained-random test
//     T10 N_RAND cycles in 6 traffic phases, random thresholds, random
//         single/double fault injection, random status clears.
//
//   Plusargs: +seed=<n>  +vcd  +sat
//   Parameters (override with -P): DATA_W, DEPTH, ECC_EN, N_RAND
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_sync_fifo_ecc;
    parameter integer DATA_W = 32;
    parameter integer DEPTH  = 16;
    parameter integer ECC_EN = 1;
    parameter integer N_RAND = 50000;

    localparam integer ADDR_W = $clog2(DEPTH);
    localparam integer PAR_W  = $clog2(DATA_W + $clog2(DATA_W) + 1);
    localparam integer CW_W   = DATA_W + PAR_W + 1;
    localparam integer MEM_W  = (ECC_EN != 0) ? CW_W : DATA_W;

    //------------------------------------------------------------------
    // DUT signals
    //------------------------------------------------------------------
    reg               clk = 1'b0;
    reg               rst_n = 1'b0;
    reg               wr_en = 1'b0, rd_en = 1'b0;
    reg  [DATA_W-1:0] wr_data = {DATA_W{1'b0}};
    reg  [ADDR_W:0]   af_thresh, ae_thresh;
    reg               clr_status = 1'b0;
    reg               inj_en = 1'b0;
    reg  [CW_W-1:0]   inj_mask = {CW_W{1'b0}};

    wire [DATA_W-1:0] rd_data;
    wire              rd_valid, full, empty, almost_full, almost_empty;
    wire [ADDR_W:0]   count;
    wire              overflow, underflow, sec_err, ded_err;
    wire [15:0]       sec_cnt, ded_cnt;

    always #5 clk = ~clk;      // 100 MHz

    sync_fifo_ecc #(.DATA_W(DATA_W), .DEPTH(DEPTH), .ECC_EN(ECC_EN)) dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_data(wr_data),
        .rd_en(rd_en), .rd_data(rd_data), .rd_valid(rd_valid),
        .full(full), .empty(empty),
        .almost_full(almost_full), .almost_empty(almost_empty),
        .count(count), .af_thresh(af_thresh), .ae_thresh(ae_thresh),
        .overflow(overflow), .underflow(underflow),
        .sec_err(sec_err), .ded_err(ded_err),
        .sec_cnt(sec_cnt), .ded_cnt(ded_cnt), .clr_status(clr_status),
        .inj_en(inj_en), .inj_mask(inj_mask)
    );

    //------------------------------------------------------------------
    // reference model state
    //------------------------------------------------------------------
    reg [DATA_W-1:0] m_q    [0:DEPTH-1];   // original data
    reg [CW_W-1:0]   m_mask [0:DEPTH-1];   // injected mask
    integer          m_head, m_tail, m_cnt;
    reg              m_rd_valid, m_ovf, m_udf;
    reg [DATA_W-1:0] m_exp_data;
    reg [CW_W-1:0]   m_exp_mask;
    integer          m_sec_cnt, m_ded_cnt;

    // statistics / functional coverage
    integer n_cycles, n_wr, n_rd, n_checks, n_err;
    integer cv_full, cv_empty, cv_wthru, cv_ovf_try, cv_udf_try, cv_simul;
    integer cv_af_rise, cv_ae_rise, cv_max_occ, cv_clr;
    integer cv_inj1, cv_inj2, cv_sec_seen, cv_ded_seen, cv_silent;
    reg [CW_W-1:0] cv_bitpos;              // single-fault positions hit
    reg            p_af, p_ae;
    integer seed, i, k, ph, p_w, p_r, p_inj;

    function integer popcount(input [CW_W-1:0] v);
        integer b;
        begin
            popcount = 0;
            for (b = 0; b < CW_W; b = b + 1) popcount = popcount + v[b];
        end
    endfunction

    task check(input [255:0] name, input [63:0] got, input [63:0] exp);
        begin
            n_checks = n_checks + 1;
            if (got !== exp) begin
                n_err = n_err + 1;
                if (n_err <= 20)
                    $display("[%0t] MISMATCH %0s : dut=%0h model=%0h", $time, name, got, exp);
                if (n_err >= 500) begin
                    $display(" mismatches                      : %0d (aborted)", n_err);
                    $display(" RESULT: FAIL");
                    $finish;
                end
            end
        end
    endtask

    //------------------------------------------------------------------
    // one clock: drive at negedge, update model at posedge, compare
    //------------------------------------------------------------------
    task cycle(input w, input [DATA_W-1:0] d, input r,
               input [CW_W-1:0] mask, input clr);
        reg m_wr_fire, m_rd_fire, pre_valid;
        reg [CW_W-1:0] pre_mask;
        integer pc;
        begin
            @(negedge clk);
            wr_en = w; wr_data = d; rd_en = r;
            inj_en = (mask != 0); inj_mask = mask; clr_status = clr;
            @(posedge clk);
            // ---- model (uses pre-edge model state) ------------------
            m_rd_fire = r & (m_cnt != 0);
            m_wr_fire = w & ((m_cnt != DEPTH) | r);
            pre_valid = m_rd_valid;
            pre_mask  = m_exp_mask;
            // counters / sticky flags: clear has priority
            if (clr) begin
                m_ovf = 0; m_udf = 0; m_sec_cnt = 0; m_ded_cnt = 0;
                cv_clr = cv_clr + 1;
            end else begin
                if (w & ~m_wr_fire) m_ovf = 1;
                if (r & (m_cnt == 0)) m_udf = 1;
                if (ECC_EN != 0 && pre_valid) begin
                    pc = popcount(pre_mask);
                    if (pc == 1 && m_sec_cnt < 65535) m_sec_cnt = m_sec_cnt + 1;
                    if (pc == 2 && m_ded_cnt < 65535) m_ded_cnt = m_ded_cnt + 1;
                end
            end
            if (m_rd_fire) begin
                m_exp_data = m_q[m_head];
                m_exp_mask = m_mask[m_head];
                m_head = (m_head + 1) % DEPTH;
            end
            if (m_wr_fire) begin
                m_q[m_tail]    = d;
                m_mask[m_tail] = mask;
                m_tail = (m_tail + 1) % DEPTH;
            end
            m_cnt = m_cnt + m_wr_fire - m_rd_fire;
            m_rd_valid = m_rd_fire;

            // ---- coverage ------------------------------------------
            n_cycles = n_cycles + 1;
            if (m_wr_fire) n_wr = n_wr + 1;
            if (m_rd_fire) n_rd = n_rd + 1;
            if (w & r)     cv_simul = cv_simul + 1;
            if (w & ~m_wr_fire) cv_ovf_try = cv_ovf_try + 1;
            if (r & ~m_rd_fire) cv_udf_try = cv_udf_try + 1;
            if (m_wr_fire & (m_cnt == DEPTH) & m_rd_fire) cv_wthru = cv_wthru + 1;
            if (m_cnt > cv_max_occ) cv_max_occ = m_cnt;
            if (m_wr_fire && popcount(mask) == 1) begin
                cv_inj1 = cv_inj1 + 1; cv_bitpos = cv_bitpos | mask;
            end
            if (m_wr_fire && popcount(mask) == 2) cv_inj2 = cv_inj2 + 1;

            // ---- compare -------------------------------------------
            #1;
            check("count",        count,        m_cnt);
            check("full",         full,         m_cnt == DEPTH);
            check("empty",        empty,        m_cnt == 0);
            check("almost_full",  almost_full,  m_cnt >= af_thresh);
            check("almost_empty", almost_empty, m_cnt <= ae_thresh);
            check("rd_valid",     rd_valid,     m_rd_valid);
            check("overflow",     overflow,     m_ovf);
            check("underflow",    underflow,    m_udf);
            check("sec_cnt",      sec_cnt,      m_sec_cnt);
            check("ded_cnt",      ded_cnt,      m_ded_cnt);
            if (full)  cv_full  = cv_full + 1;
            if (empty) cv_empty = cv_empty + 1;
            if (almost_full  & ~p_af) cv_af_rise = cv_af_rise + 1;
            if (almost_empty & ~p_ae) cv_ae_rise = cv_ae_rise + 1;
            p_af = almost_full; p_ae = almost_empty;

            if (m_rd_valid) begin
                pc = popcount(m_exp_mask);
                if (ECC_EN != 0) begin
                    check("sec_err", sec_err, pc == 1);
                    check("ded_err", ded_err, pc == 2);
                    if (pc <= 1) check("rd_data", rd_data, m_exp_data);
                    if (sec_err) cv_sec_seen = cv_sec_seen + 1;
                    if (ded_err) cv_ded_seen = cv_ded_seen + 1;
                end else begin
                    // unprotected: the fault reaches the output unchanged
                    check("rd_data", rd_data, m_exp_data ^ m_exp_mask[DATA_W-1:0]);
                    check("sec_err", sec_err, 1'b0);
                    check("ded_err", ded_err, 1'b0);
                    if (rd_data !== m_exp_data) cv_silent = cv_silent + 1;
                end
            end else begin
                check("sec_err(idle)", sec_err, 1'b0);
                check("ded_err(idle)", ded_err, 1'b0);
            end
        end
    endtask

    task idle(input integer n);
        integer c;
        begin
            for (c = 0; c < n; c = c + 1) cycle(0, 0, 0, 0, 0);
        end
    endtask

    // bounded drain: never hangs even if the DUT never reports empty
    task drain;
        integer g;
        begin
            g = 0;
            while (!empty && g < 4*DEPTH) begin
                cycle(0, 0, 1, 0, 0);
                g = g + 1;
            end
        end
    endtask

    function [DATA_W-1:0] rnd_data(input dummy);
        begin
            rnd_data = {$random(seed), $random(seed), $random(seed), $random(seed)};
        end
    endfunction

    function [CW_W-1:0] bit1(input integer p);
        begin
            bit1 = {{(CW_W-1){1'b0}}, 1'b1} << p;
        end
    endfunction

    //------------------------------------------------------------------
    // main sequence
    //------------------------------------------------------------------
    reg [CW_W-1:0] mk;
    integer a, b, rr;
    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 20261022;
        if ($test$plusargs("vcd")) begin
            $dumpfile("sync_fifo_ecc.vcd");
            $dumpvars(0, tb_sync_fifo_ecc);
        end
        n_cycles = 0; n_wr = 0; n_rd = 0; n_checks = 0; n_err = 0;
        cv_full = 0; cv_empty = 0; cv_wthru = 0; cv_ovf_try = 0; cv_udf_try = 0;
        cv_simul = 0; cv_af_rise = 0; cv_ae_rise = 0; cv_max_occ = 0; cv_clr = 0;
        cv_inj1 = 0; cv_inj2 = 0; cv_sec_seen = 0; cv_ded_seen = 0; cv_silent = 0;
        cv_bitpos = 0; p_af = 0; p_ae = 1;
        m_head = 0; m_tail = 0; m_cnt = 0; m_rd_valid = 0; m_ovf = 0; m_udf = 0;
        m_exp_data = 0; m_exp_mask = 0; m_sec_cnt = 0; m_ded_cnt = 0;
        af_thresh = DEPTH - 2;
        ae_thresh = 2;

        $display("==============================================================");
        $display(" tb_sync_fifo_ecc  DATA_W=%0d DEPTH=%0d ECC_EN=%0d CW_W=%0d seed=%0d",
                 DATA_W, DEPTH, ECC_EN, CW_W, seed);
        $display("==============================================================");

        // ---- T1 reset ------------------------------------------------
        #23 rst_n = 1'b1;
        #1;
        check("rst count", count, 0);       check("rst empty", empty, 1);
        check("rst full", full, 0);         check("rst rd_valid", rd_valid, 0);
        check("rst ovf", overflow, 0);      check("rst udf", underflow, 0);
        idle(2);
        $display("T1  reset state                       done  (errors so far %0d)", n_err);

        // ---- T2 fill + overflow ---------------------------------------
        for (i = 0; i < DEPTH + 2; i = i + 1) cycle(1, 32'hA0000000 + i, 0, 0, 0);
        check("T2 full", full, 1);
        check("T2 overflow", overflow, 1);
        $display("T2  fill to full + 2 overflow writes  done  (errors so far %0d)", n_err);

        // ---- T3 write-through while full ------------------------------
        for (i = 0; i < 2 * DEPTH; i = i + 1) cycle(1, 32'hB0000000 + i, 1, 0, 0);
        check("T3 still full", full, 1);
        $display("T3  simultaneous R/W at full          done  (errors so far %0d)", n_err);

        // ---- T4 drain + underflow -------------------------------------
        for (i = 0; i < DEPTH + 3; i = i + 1) cycle(0, 0, 1, 0, 0);
        idle(1);
        check("T4 empty", empty, 1);
        check("T4 underflow", underflow, 1);
        cycle(1, 32'hC0FFEE00, 1, 0, 0);   // read on empty with write: write only
        cycle(0, 0, 1, 0, 0);
        idle(1);
        $display("T4  drain + underflow, R/W at empty   done  (errors so far %0d)", n_err);

        // ---- T8 status clear ------------------------------------------
        cycle(0, 0, 0, 0, 1);
        check("T8 ovf clr", overflow, 0);
        check("T8 udf clr", underflow, 0);
        $display("T8  sticky status clear               done  (errors so far %0d)", n_err);

        // ---- T5 threshold sweep ---------------------------------------
        for (a = 0; a <= DEPTH; a = a + 1) begin
            af_thresh = a;
            ae_thresh = DEPTH - a;
            for (i = 0; i < DEPTH; i = i + 1) cycle(1, rnd_data(0), 0, 0, 0);
            for (i = 0; i < DEPTH; i = i + 1) cycle(0, 0, 1, 0, 0);
            idle(1);
        end
        af_thresh = DEPTH - 2; ae_thresh = 2;
        $display("T5  AF/AE threshold sweep (%0d values) done  (errors so far %0d)", DEPTH+1, n_err);

        // ---- T6 single-bit fault at every codeword position -----------
        for (a = 0; a < MEM_W; a = a + 1) begin
            cycle(1, rnd_data(0), 0, bit1(a), 0);
            if (count == DEPTH) begin
                for (i = 0; i < DEPTH; i = i + 1) cycle(0, 0, 1, 0, 0);
            end
        end
        drain;
        idle(2);
        if ($test$plusargs("vcd")) $dumpoff;
        $display("T6  single-bit fault, all %0d bit positions done  (errors so far %0d)", MEM_W, n_err);

        // ---- T7 double-bit faults -------------------------------------
        for (i = 0; i < 200; i = i + 1) begin
            a = {$random(seed)} % MEM_W;
            b = (a + 1 + ({$random(seed)} % (MEM_W - 1))) % MEM_W;
            cycle(1, rnd_data(0), (i % 3 == 0), bit1(a) | bit1(b), 0);
        end
        drain;
        idle(2);
        $display("T7  200 double-bit faults             done  (errors so far %0d)", n_err);

        // ---- T9 SEC counter saturation --------------------------------
        if (ECC_EN != 0 && $test$plusargs("sat")) begin
            for (i = 0; i < 65540; i = i + 1)
                cycle(1, rnd_data(0), 1, bit1(i % CW_W), 0);
            drain;
            idle(2);
            check("T9 sec_cnt saturated", sec_cnt, 16'hFFFF);
            $display("T9  SEC counter saturation (65540 ev) done  (errors so far %0d)", n_err);
        end
        cycle(0, 0, 0, 0, 1);

        // ---- T10 constrained random -----------------------------------
        for (ph = 0; ph < 6; ph = ph + 1) begin
            case (ph)
                0: begin p_w = 90; p_r = 10; end   // fill-biased
                1: begin p_w = 10; p_r = 90; end   // drain-biased
                2: begin p_w = 50; p_r = 50; end   // balanced
                3: begin p_w = 100; p_r = 100; end // full streaming
                4: begin p_w = 70; p_r = 60; end   // hovering near full
                default: begin p_w = 40; p_r = 45; end
            endcase
            for (k = 0; k < N_RAND / 6; k = k + 1) begin
                if (({$random(seed)} % 500) == 0) begin
                    af_thresh = {$random(seed)} % (DEPTH + 1);
                    ae_thresh = {$random(seed)} % (DEPTH + 1);
                end
                rr = {$random(seed)} % 1000;
                if (rr < 15)       mk = bit1({$random(seed)} % MEM_W);              // 1.5 %
                else if (rr < 20) begin                                            // 0.5 %
                    a = {$random(seed)} % MEM_W;
                    b = (a + 1 + ({$random(seed)} % (MEM_W - 1))) % MEM_W;
                    mk = bit1(a) | bit1(b);
                end else           mk = 0;
                cycle(({$random(seed)} % 100) < p_w, rnd_data(0),
                      ({$random(seed)} % 100) < p_r, mk,
                      ({$random(seed)} % 2000) == 0);
            end
            $display("T10 random phase %0d (pW=%0d%% pR=%0d%%) done  (errors so far %0d)",
                     ph, p_w, p_r, n_err);
        end
        drain;
        idle(2);

        // ---- report ---------------------------------------------------
        $display("--------------------------------------------------------------");
        $display(" SUMMARY");
        $display("   clock cycles simulated          : %0d", n_cycles);
        $display("   writes accepted / reads accepted: %0d / %0d", n_wr, n_rd);
        $display("   scoreboard comparisons          : %0d", n_checks);
        $display("   mismatches                      : %0d", n_err);
        $display(" FUNCTIONAL COVERAGE");
        $display("   cycles full / empty             : %0d / %0d", cv_full, cv_empty);
        $display("   max occupancy reached           : %0d of %0d", cv_max_occ, DEPTH);
        $display("   write-through at full           : %0d", cv_wthru);
        $display("   blocked writes / blocked reads  : %0d / %0d", cv_ovf_try, cv_udf_try);
        $display("   simultaneous wr_en & rd_en      : %0d", cv_simul);
        $display("   almost_full / almost_empty rises: %0d / %0d", cv_af_rise, cv_ae_rise);
        $display("   status clears                   : %0d", cv_clr);
        $display("   single / double faults injected : %0d / %0d", cv_inj1, cv_inj2);
        $display("   codeword bit positions covered  : %0d of %0d",
                 popcount(cv_bitpos & ({CW_W{1'b1}} >> (CW_W - MEM_W))), MEM_W);
        if (ECC_EN != 0)
            $display("   SEC events / DED events seen    : %0d / %0d", cv_sec_seen, cv_ded_seen);
        else
            $display("   silently corrupted reads (no ECC): %0d", cv_silent);
        $display("   final sec_cnt / ded_cnt          : %0d / %0d", sec_cnt, ded_cnt);
        if (n_err == 0) $display(" RESULT: PASS");
        else            $display(" RESULT: FAIL");
        $display("==============================================================");
        $finish;
    end

    // watchdog
    initial begin
        #200_000_000;
        $display("ERROR: watchdog timeout");
        $finish;
    end
endmodule
