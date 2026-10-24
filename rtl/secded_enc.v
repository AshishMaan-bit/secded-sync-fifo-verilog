//-----------------------------------------------------------------------------
// File        : secded_enc.v
// Project     : SECDED-Protected Synchronous FIFO with Programmable Thresholds
// Description : Parameterised extended-Hamming SECDED encoder.
//
//   Codeword layout (CW_W = DATA_W + PAR_W + 1 bits):
//     cw[0]            : overall (even) parity over cw[HAM_W:1]
//     cw[2^j], j<PAR_W : Hamming check bit j
//     cw[other]        : data bits, packed LSB first
//
//   PAR_W is the smallest P with 2^P >= DATA_W + P + 1. The default
//   expression below gives that value for every DATA_W in 1..120
//   (checked exhaustively by tb_secded.v at elaboration of each width used).
//
//   Fully combinational: loops are unrolled at elaboration time.
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module secded_enc #(
    parameter integer DATA_W = 32,
    parameter integer PAR_W  = $clog2(DATA_W + $clog2(DATA_W) + 1),
    parameter integer CW_W   = DATA_W + PAR_W + 1
)(
    input  wire [DATA_W-1:0] data_i,
    output wire [CW_W-1:0]   cw_o
);
    localparam integer HAM_W = DATA_W + PAR_W;   // Hamming positions 1..HAM_W

    reg [HAM_W:0] c;
    integer i, j, k;

    always @* begin
        c = {(HAM_W+1){1'b0}};
        // 1) scatter data bits into the non power-of-two positions
        k = 0;
        for (i = 1; i <= HAM_W; i = i + 1) begin
            if ((i & (i - 1)) != 0) begin
                c[i] = data_i[k];
                k    = k + 1;
            end
        end
        // 2) Hamming check bit j = XOR of every position whose index has bit j set
        for (j = 0; j < PAR_W; j = j + 1) begin
            for (i = 1; i <= HAM_W; i = i + 1) begin
                if ((((i >> j) & 1) == 1) && (i != (1 << j)))
                    c[1 << j] = c[1 << j] ^ c[i];
            end
        end
        // 3) overall parity bit makes the whole codeword even parity
        c[0] = ^c[HAM_W:1];
    end

    assign cw_o = c;

endmodule
