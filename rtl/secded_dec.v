//-----------------------------------------------------------------------------
// File        : secded_dec.v
// Project     : SECDED-Protected Synchronous FIFO with Programmable Thresholds
// Description : Parameterised extended-Hamming SECDED decoder (companion of
//               secded_enc.v).
//
//   syndrome == 0, overall parity == 0  -> no error
//   overall parity == 1, syndrome <= HAM_W -> single-bit error, corrected
//                                             (syndrome == 0 -> error was in
//                                              the overall parity bit itself)
//   overall parity == 0, syndrome != 0  -> double-bit error, detected (DED)
//   overall parity == 1, syndrome >  HAM_W -> impossible single error,
//                                             reported as uncorrectable (DED)
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module secded_dec #(
    parameter integer DATA_W = 32,
    parameter integer PAR_W  = $clog2(DATA_W + $clog2(DATA_W) + 1),
    parameter integer CW_W   = DATA_W + PAR_W + 1
)(
    input  wire [CW_W-1:0]   cw_i,
    output reg  [DATA_W-1:0] data_o,
    output reg               sec_o,       // single error corrected
    output reg               ded_o,       // double (uncorrectable) error
    output reg  [PAR_W-1:0]  syndrome_o
);
    localparam integer HAM_W = DATA_W + PAR_W;

    reg  [HAM_W:0]  fixed;
    reg  [PAR_W-1:0] syn;
    reg              ovp;
    integer i, j, k, syn_i;

    always @* begin
        // syndrome
        syn = {PAR_W{1'b0}};
        for (j = 0; j < PAR_W; j = j + 1)
            for (i = 1; i <= HAM_W; i = i + 1)
                if (((i >> j) & 1) == 1)
                    syn[j] = syn[j] ^ cw_i[i];
        ovp   = ^cw_i;
        syn_i = {{(32-PAR_W){1'b0}}, syn};

        fixed = cw_i;
        sec_o = 1'b0;
        ded_o = 1'b0;

        if (ovp) begin
            if (syn_i <= HAM_W) begin
                sec_o = 1'b1;
                for (i = 0; i <= HAM_W; i = i + 1)
                    if (syn_i == i) fixed[i] = ~fixed[i];
            end else begin
                ded_o = 1'b1;
            end
        end else if (syn != {PAR_W{1'b0}}) begin
            ded_o = 1'b1;
        end

        // gather data bits
        data_o = {DATA_W{1'b0}};
        k = 0;
        for (i = 1; i <= HAM_W; i = i + 1) begin
            if ((i & (i - 1)) != 0) begin
                data_o[k] = fixed[i];
                k         = k + 1;
            end
        end
        syndrome_o = syn;
    end

endmodule
