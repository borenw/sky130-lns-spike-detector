// Multiplier-free SUBTRACTION kernel via the LNS rearrangement:
//   (A*B - C*D) > Vth   <=>   A*B > C*D + Vth
// So: fold Vth into C*D with one LNS add, w = log2(C*D + Vth), then compare
//   out = ( log2(A*B) > w ).  Reuses lod5.v, lns_add.v, lns_ftable.v.  Vth programmable, >=0.
`default_nettype none
module log_sub #(
    parameter WIDTH = 10,
    parameter K     = 2,
    parameter VW    = 21
) (
    input  wire             clk,
    input  wire [WIDTH-1:0] A, B, C, D,
    input  wire [VW-1:0]    Vth,
    output reg              out
);
    reg [WIDTH-1:0] Ar, Br, Cr, Dr;
    reg [VW-1:0]    Vr;
    always @(posedge clk) begin
        Ar <= A; Br <= B; Cr <= C; Dr <= D; Vr <= Vth;
    end

    wire [$clog2(WIDTH)-1:0] eA, eB, eC, eD;
    wire [K-1:0]             fA, fB, fC, fD;
    wire                     zA, zB, zC, zD;
    lod #(.N(WIDTH), .FR(K)) LA (.v(Ar), .e(eA), .frac(fA), .is_zero(zA));
    lod #(.N(WIDTH), .FR(K)) LB (.v(Br), .e(eB), .frac(fB), .is_zero(zB));
    lod #(.N(WIDTH), .FR(K)) LC (.v(Cr), .e(eC), .frac(fC), .is_zero(zC));
    lod #(.N(WIDTH), .FR(K)) LD (.v(Dr), .e(eD), .frac(fD), .is_zero(zD));
    wire [$clog2(VW)-1:0]    eV;
    wire [K-1:0]             fV;
    wire                     zV;
    lod #(.N(VW), .FR(K)) LV (.v(Vr), .e(eV), .frac(fV), .is_zero(zV));

    wire [7:0] La = {eA, fA}, Lb = {eB, fB}, Lc = {eC, fC}, Ld = {eD, fD}, Lv = {eV, fV};
    wire [7:0] X  = La + Lb;              // log2(A*B)
    wire [7:0] Y  = Lc + Ld;              // log2(C*D)
    wire       zx = zA | zB;             // A*B == 0
    wire       zy = zC | zD;             // C*D == 0

    // w = log2(C*D + Vth) = LNS_add(Y, log2 Vth)
    wire [8:0] w;
    wire       w_zero;
    lns_add #(.LW(8)) ADD (.X(Y), .Y(Lv), .zx(zy), .zy(zV), .s(w), .s_zero(w_zero));

    // out = ( A*B > C*D + Vth )  <=>  ( X > w )
    reg out_c;
    always @* begin
        if (zx)          out_c = 1'b0;                  // A*B = 0 can't exceed (C*D+Vth) >= 0
        else if (w_zero) out_c = 1'b1;                  // C*D + Vth = 0, and A*B > 0
        else             out_c = (X > w) ? 1'b1 : 1'b0;
    end
    always @(posedge clk) out <= out_c;
endmodule
`default_nettype wire
