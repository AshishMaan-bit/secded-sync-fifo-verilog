//-----------------------------------------------------------------------------
// File        : tb_secded.v
// Description : Self-checking unit test of the SECDED encoder/decoder pair.
//   For DATA_W given by -P tb_secded.DATA_W=<n>:
//     * checks PAR_W is the minimum number of Hamming check bits
//     * N_VEC data words (exhaustive if DATA_W <= 10, otherwise random +
//       corner patterns):
//         - no-error decode  -> data equal, sec=0, ded=0
//         - every single-bit flip of the codeword -> corrected, sec=1, ded=0
//         - every double-bit flip (first N_DBL words) -> ded=1, sec=0
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_secded;
    parameter integer DATA_W = 32;
    parameter integer N_VEC  = 2000;
    parameter integer N_DBL  = 40;
    localparam integer PAR_W = $clog2(DATA_W + $clog2(DATA_W) + 1);
    localparam integer CW_W  = DATA_W + PAR_W + 1;

    reg  [DATA_W-1:0] data;
    wire [CW_W-1:0]   cw;
    reg  [CW_W-1:0]   cw_bad;
    wire [DATA_W-1:0] dout;
    wire              sec, ded;
    wire [PAR_W-1:0]  syn;

    secded_enc #(.DATA_W(DATA_W)) u_enc (.data_i(data), .cw_o(cw));
    secded_dec #(.DATA_W(DATA_W)) u_dec (.cw_i(cw_bad), .data_o(dout),
                                          .sec_o(sec), .ded_o(ded),
                                          .syndrome_o(syn));

    integer v, a, b, nvec, errors, n_clean, n_single, n_double, seed;

    task fail(input [255:0] what);
        begin
            errors = errors + 1;
            if (errors < 10)
                $display("ERROR[%0s] data=%h cw=%h bad=%h dout=%h sec=%b ded=%b syn=%0d",
                         what, data, cw, cw_bad, dout, sec, ded, syn);
        end
    endtask

    initial begin
        errors = 0; n_clean = 0; n_single = 0; n_double = 0; seed = 32'h5EC0DED;
        // ---- minimality of PAR_W ------------------------------------
        if (!((1 << PAR_W) >= DATA_W + PAR_W + 1) ||
             ((1 << (PAR_W-1)) >= DATA_W + PAR_W))
        begin
            $display("ERROR: PAR_W=%0d not minimal for DATA_W=%0d", PAR_W, DATA_W);
            errors = errors + 1;
        end

        nvec = (DATA_W <= 10) ? (1 << DATA_W) : N_VEC;

        for (v = 0; v < nvec; v = v + 1) begin
            // stimulus: exhaustive, or corner patterns then random
            if (DATA_W <= 10)              data = v;
            else if (v == 0)               data = {DATA_W{1'b0}};
            else if (v == 1)               data = {DATA_W{1'b1}};
            else if (v == 2)               data = {(DATA_W+1)/2{2'b01}};
            else if (v == 3)               data = {(DATA_W+1)/2{2'b10}};
            else if (v < 4 + DATA_W)       data = {{(DATA_W-1){1'b0}},1'b1} << (v-4);
            else begin
                data = {$random(seed), $random(seed), $random(seed), $random(seed)};
            end

            // clean
            #1 cw_bad = cw; #1;
            n_clean = n_clean + 1;
            if (dout !== data || sec !== 1'b0 || ded !== 1'b0) fail("clean");

            // single-bit errors
            for (a = 0; a < CW_W; a = a + 1) begin
                cw_bad = cw ^ ({{(CW_W-1){1'b0}},1'b1} << a); #1;
                n_single = n_single + 1;
                if (dout !== data || sec !== 1'b1 || ded !== 1'b0) fail("single");
            end

            // double-bit errors
            if (v < N_DBL || DATA_W <= 10) begin
                for (a = 0; a < CW_W; a = a + 1)
                    for (b = a + 1; b < CW_W; b = b + 1) begin
                        cw_bad = cw ^ ({{(CW_W-1){1'b0}},1'b1} << a)
                                    ^ ({{(CW_W-1){1'b0}},1'b1} << b); #1;
                        n_double = n_double + 1;
                        if (ded !== 1'b1 || sec !== 1'b0) fail("double");
                    end
            end
        end

        $display("--------------------------------------------------------------");
        $display(" SECDED unit test  DATA_W=%0d  PAR_W=%0d  CW_W=%0d", DATA_W, PAR_W, CW_W);
        $display("   clean words checked      : %0d", n_clean);
        $display("   single-bit errors checked: %0d", n_single);
        $display("   double-bit errors checked: %0d", n_double);
        $display("   mismatches               : %0d", errors);
        if (errors == 0) $display(" RESULT: PASS");
        else             $display(" RESULT: FAIL");
        $display("--------------------------------------------------------------");
        $finish;
    end
endmodule
