//-----------------------------------------------------------------------------
// File        : fifo_baseline.v
// Project     : SECDED-Protected Synchronous FIFO with Programmable Thresholds
// Description : Conventional single-clock FIFO used as the reference design
//               for area / logic-depth comparison. (N+1)-bit pointer scheme:
//               the extra MSB distinguishes full from empty.
//               Write when full and read when empty are ignored.
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
module fifo_baseline #(
    parameter integer DATA_W = 32,
    parameter integer DEPTH  = 16,                  // must be a power of 2
    parameter integer ADDR_W = $clog2(DEPTH)
)(
    input  wire              clk,
    input  wire              rst_n,
    input  wire              wr_en,
    input  wire [DATA_W-1:0] wr_data,
    input  wire              rd_en,
    output reg  [DATA_W-1:0] rd_data,
    output reg               rd_valid,
    output wire              full,
    output wire              empty
);
    reg [DATA_W-1:0] mem [0:DEPTH-1];
    reg [ADDR_W:0]   wr_ptr, rd_ptr;

    wire wr_fire = wr_en & ~full;
    wire rd_fire = rd_en & ~empty;

    assign empty = (wr_ptr == rd_ptr);
    assign full  = (wr_ptr[ADDR_W] != rd_ptr[ADDR_W]) &&
                   (wr_ptr[ADDR_W-1:0] == rd_ptr[ADDR_W-1:0]);

    always @(posedge clk) begin
        if (wr_fire) mem[wr_ptr[ADDR_W-1:0]] <= wr_data;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr   <= {(ADDR_W+1){1'b0}};
            rd_ptr   <= {(ADDR_W+1){1'b0}};
            rd_data  <= {DATA_W{1'b0}};
            rd_valid <= 1'b0;
        end else begin
            rd_valid <= rd_fire;
            if (wr_fire) wr_ptr <= wr_ptr + 1'b1;
            if (rd_fire) begin
                rd_ptr  <= rd_ptr + 1'b1;
                rd_data <= mem[rd_ptr[ADDR_W-1:0]];
            end
        end
    end

endmodule
