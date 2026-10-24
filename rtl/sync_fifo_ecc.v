//-----------------------------------------------------------------------------
// File        : sync_fifo_ecc.v
// Project     : SECDED-Protected Synchronous FIFO with Programmable Thresholds
// Description : Single-clock FIFO with
//   (1) optional extended-Hamming SECDED protection of the storage array
//       (ECC_EN=1): single-bit upsets are corrected on the fly, double-bit
//       upsets are flagged;
//   (2) run-time programmable almost-full / almost-empty thresholds;
//   (3) registered, glitch-free status flags computed from the NEXT
//       occupancy value (no pointer comparators on the flag outputs);
//   (4) write-through-when-full: a write is accepted while full if a read
//       happens in the same cycle (sustains 100% throughput at full);
//   (5) sticky overflow / underflow flags and saturating SEC / DED event
//       counters with a synchronous clear;
//   (6) a fault-injection port (XOR mask on the stored codeword) so that the
//       ECC path can be verified in simulation and exercised in silicon BIST.
//
// Read latency: rd_data / rd_valid / sec_err / ded_err are valid one clock
// after an accepted rd_en (standard, non-FWFT behaviour).
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module sync_fifo_ecc #(
    parameter integer DATA_W = 32,
    parameter integer DEPTH  = 16,                  // power of 2, >= 2
    parameter integer ECC_EN = 1,                   // 1: SECDED on, 0: off
    parameter integer ADDR_W = $clog2(DEPTH),
    parameter integer PAR_W  = $clog2(DATA_W + $clog2(DATA_W) + 1),
    parameter integer CW_W   = DATA_W + PAR_W + 1
)(
    input  wire              clk,
    input  wire              rst_n,          // asynchronous active-low reset
    // write port
    input  wire              wr_en,
    input  wire [DATA_W-1:0] wr_data,
    // read port
    input  wire              rd_en,
    output wire [DATA_W-1:0] rd_data,
    output reg               rd_valid,
    // status
    output reg               full,
    output reg               empty,
    output reg               almost_full,    // count >= af_thresh
    output reg               almost_empty,   // count <= ae_thresh
    output reg  [ADDR_W:0]   count,
    input  wire [ADDR_W:0]   af_thresh,
    input  wire [ADDR_W:0]   ae_thresh,
    // error reporting
    output reg               overflow,       // sticky
    output reg               underflow,      // sticky
    output wire              sec_err,        // qualified by rd_valid
    output wire              ded_err,        // qualified by rd_valid
    output reg  [15:0]       sec_cnt,        // saturating
    output reg  [15:0]       ded_cnt,        // saturating
    input  wire              clr_status,
    // fault injection (test only)
    input  wire              inj_en,
    input  wire [CW_W-1:0]   inj_mask
);
    localparam integer MEM_W = (ECC_EN != 0) ? CW_W : DATA_W;
    localparam [ADDR_W:0] DEPTH_V = DEPTH[ADDR_W:0];

    //------------------------------------------------------------------
    // handshake
    //------------------------------------------------------------------
    wire rd_fire = rd_en & ~empty;
    wire wr_fire = wr_en & (~full | rd_en);   // write-through when full

    reg [ADDR_W-1:0] wr_ptr, rd_ptr;

    wire [ADDR_W:0] count_nxt = count + {{ADDR_W{1'b0}}, wr_fire}
                                      - {{ADDR_W{1'b0}}, rd_fire};

    //------------------------------------------------------------------
    // encode + optional fault injection
    //------------------------------------------------------------------
    wire [MEM_W-1:0] wr_word;
    wire [MEM_W-1:0] rd_word;
    reg  [MEM_W-1:0] rd_word_q;
    wire             dec_sec, dec_ded;
    wire [DATA_W-1:0] dec_data;

    generate
        if (ECC_EN != 0) begin : g_ecc
            wire [CW_W-1:0] cw;
            wire [PAR_W-1:0] syn_unused;
            secded_enc #(.DATA_W(DATA_W), .PAR_W(PAR_W), .CW_W(CW_W)) u_enc (
                .data_i (wr_data),
                .cw_o   (cw)
            );
            assign wr_word = cw ^ (inj_en ? inj_mask : {CW_W{1'b0}});

            secded_dec #(.DATA_W(DATA_W), .PAR_W(PAR_W), .CW_W(CW_W)) u_dec (
                .cw_i       (rd_word_q),
                .data_o     (dec_data),
                .sec_o      (dec_sec),
                .ded_o      (dec_ded),
                .syndrome_o (syn_unused)
            );
        end else begin : g_noecc
            assign wr_word  = wr_data ^ (inj_en ? inj_mask[DATA_W-1:0]
                                                : {DATA_W{1'b0}});
            assign dec_data = rd_word_q;
            assign dec_sec  = 1'b0;
            assign dec_ded  = 1'b0;
            // check-bit part of inj_mask has no storage when ECC is off
            wire unused_inj_hi = ^inj_mask;
        end
    endgenerate

    //------------------------------------------------------------------
    // storage array (no reset -> maps to RAM / latch array)
    //------------------------------------------------------------------
    reg [MEM_W-1:0] mem [0:DEPTH-1];

    always @(posedge clk) begin
        if (wr_fire) mem[wr_ptr] <= wr_word;
    end
    assign rd_word = mem[rd_ptr];

    //------------------------------------------------------------------
    // pointers, occupancy, registered flags, read register
    //------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr       <= {ADDR_W{1'b0}};
            rd_ptr       <= {ADDR_W{1'b0}};
            count        <= {(ADDR_W+1){1'b0}};
            full         <= 1'b0;
            empty        <= 1'b1;
            almost_full  <= 1'b0;
            almost_empty <= 1'b1;
            rd_valid     <= 1'b0;
            rd_word_q    <= {MEM_W{1'b0}};
        end else begin
            if (wr_fire) wr_ptr <= wr_ptr + 1'b1;
            if (rd_fire) begin
                rd_ptr    <= rd_ptr + 1'b1;
                rd_word_q <= rd_word;
            end
            rd_valid     <= rd_fire;
            count        <= count_nxt;
            full         <= (count_nxt == DEPTH_V);
            empty        <= (count_nxt == {(ADDR_W+1){1'b0}});
            almost_full  <= (count_nxt >= af_thresh);
            almost_empty <= (count_nxt <= ae_thresh);
        end
    end

    //------------------------------------------------------------------
    // error reporting
    //------------------------------------------------------------------
    assign rd_data = dec_data;
    assign sec_err = rd_valid & dec_sec;
    assign ded_err = rd_valid & dec_ded;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            overflow  <= 1'b0;
            underflow <= 1'b0;
            sec_cnt   <= 16'd0;
            ded_cnt   <= 16'd0;
        end else if (clr_status) begin
            overflow  <= 1'b0;
            underflow <= 1'b0;
            sec_cnt   <= 16'd0;
            ded_cnt   <= 16'd0;
        end else begin
            if (wr_en & ~wr_fire)              overflow  <= 1'b1;
            if (rd_en &  empty)                underflow <= 1'b1;
            if (sec_err && (sec_cnt != 16'hFFFF)) sec_cnt <= sec_cnt + 1'b1;
            if (ded_err && (ded_cnt != 16'hFFFF)) ded_cnt <= ded_cnt + 1'b1;
        end
    end

endmodule
