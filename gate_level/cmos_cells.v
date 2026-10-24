//-----------------------------------------------------------------------------
// File        : cmos_cells.v
// Description : Transistor-level (switch-level) CMOS cell library used to
//               simulate the synthesised gate-level netlists.
//
//   Every cell is built ONLY from Verilog `nmos` / `pmos` switch primitives
//   connected to supply1 (VDD) and supply0 (GND) - i.e. exactly the static
//   CMOS circuits drawn in a VLSI textbook.
//
//      cell   function                       transistors
//      INV    Y = ~A                          2  (1 P + 1 N)
//      NAND2  Y = ~(A & B)                    4  (2 P parallel, 2 N series)
//      NOR2   Y = ~(A | B)                    4  (2 P series,   2 N parallel)
//      NAND3  Y = ~(A & B & C)                6  (used inside the flip-flops)
//      DFF    pos-edge D flip-flop            36 (6 x NAND3, classic '74 type)
//      DFFR   DFF + async active-low reset   36 (reset drives CLR_n)
//      DFFS   DFF + async active-low set     36 (reset drives PRE_n)
//
//   pmos(drain, source, gate) conducts when gate = 0
//   nmos(drain, source, gate) conducts when gate = 1
//-----------------------------------------------------------------------------
`timescale 1ns/1ps
`define TD #0.010

// Each cell = an ideal static-CMOS transistor network driving an internal node
// y, followed by a 10 ps wire delay (buf) to the output pin. The delay stands for
// the RC delay of the node; it lets the flip-flop feedback loops behave like real
// hardware instead of racing in zero time, and it filters the zero-width
// transients that a pure switch-level simulator produces while a stack switches.

module INV (input A, output Y);
    supply1 vdd; supply0 gnd;
    wire y;
    pmos mp (y, vdd, A);           // PMOS: on when A = 0, pulls y to VDD
    nmos mn (y, gnd, A);           // NMOS: on when A = 1, pulls y to GND
    buf `TD (Y, y);
endmodule

module NAND2 (input A, input B, output Y);
    supply1 vdd; supply0 gnd;
    wire y, x;                     // x = node between the two series NMOS
    pmos mpa (y, vdd, A);          // pull-up network: 2 PMOS in PARALLEL
    pmos mpb (y, vdd, B);
    nmos mna (y, x,   A);          // pull-down network: 2 NMOS in SERIES
    nmos mnb (x, gnd, B);
    buf `TD (Y, y);
endmodule

module NOR2 (input A, input B, output Y);
    supply1 vdd; supply0 gnd;
    wire y, x;                     // x = node between the two series PMOS
    pmos mpa (x, vdd, A);          // pull-up network: 2 PMOS in SERIES
    pmos mpb (y, x,   B);
    nmos mna (y, gnd, A);          // pull-down network: 2 NMOS in PARALLEL
    nmos mnb (y, gnd, B);
    buf `TD (Y, y);
endmodule

module NAND3 (input A, input B, input C, output Y);
    supply1 vdd; supply0 gnd;
    wire y, x1, x2;
    pmos mpa (y, vdd, A);          // 3 PMOS in parallel
    pmos mpb (y, vdd, B);
    pmos mpc (y, vdd, C);
    nmos mna (y,  x1, A);          // 3 NMOS in series
    nmos mnb (x1, x2, B);
    nmos mnc (x2, gnd, C);
    buf `TD (Y, y);
endmodule

// positive-edge D flip-flop with active-low preset/clear (6 x NAND3 = 36 T)
module DFF_CORE (input C, input D, input PRE_n, input CLR_n, output Q);
    wire n1, n2, n3, n4, qn;
    NAND3 g1 (.A(PRE_n), .B(n4),    .C(n2),    .Y(n1));
    NAND3 g2 (.A(n1),    .B(CLR_n), .C(C),     .Y(n2));
    NAND3 g3 (.A(n2),    .B(C),     .C(n4),    .Y(n3));
    NAND3 g4 (.A(n3),    .B(CLR_n), .C(D),     .Y(n4));
    NAND3 g5 (.A(PRE_n), .B(n2),    .C(qn),    .Y(Q));
    NAND3 g6 (.A(Q),     .B(n3),    .C(CLR_n), .Y(qn));
endmodule

module DFF (input C, input D, output Q);
    supply1 vdd;
    DFF_CORE u (.C(C), .D(D), .PRE_n(vdd), .CLR_n(vdd), .Q(Q));
endmodule

module DFFR (input C, input D, input R, output Q);   // R=0 -> Q=0
    supply1 vdd;
    DFF_CORE u (.C(C), .D(D), .PRE_n(vdd), .CLR_n(R), .Q(Q));
endmodule

module DFFS (input C, input D, input R, output Q);   // R=0 -> Q=1
    supply1 vdd;
    DFF_CORE u (.C(C), .D(D), .PRE_n(R), .CLR_n(vdd), .Q(Q));
endmodule
