// Design 2 -- log / LNS multiplier-free detector (K mantissa bits, this build K=2).
//   x = log2(A)+log2(B),  y = log2(C)+log2(D)      (K-bit log converters)
//   s = max(x,y) + F(|x-y|)                          (LNS add)
//   out = s > log2(Vth)                            (same K-bit converter on Vth)
// Same port list and same 2-cycle registered-I/O latency as mult_detector.
// Values carried in 1/2^K-log2 units: L(v) = (e<<K)+frac = {e, frac[K-1:0]}.
`default_nettype none
module log_detector #(
    parameter WIDTH = 10,
    parameter K     = 2,      // fraction (mantissa) bits (this build: 2)
    parameter VW    = 21
) (
    input  wire             clk,
    input  wire [WIDTH-1:0] A, B, C, D,
    input  wire [VW-1:0]    Vth,
    output reg              out
);
    // ---- registered inputs ----
    reg [WIDTH-1:0] Ar, Br, Cr, Dr;
    reg [VW-1:0]    Vr;
    always @(posedge clk) begin
        Ar <= A; Br <= B; Cr <= C; Dr <= D; Vr <= Vth;
    end

    // ---- K-bit log converters (LOD + K fraction bits) ----
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

    // L(v) = (e<<K) + frac = {e, frac}  (1/2^K-log2 units), zero-extended to 8 bits.
    // 8-bit buses hold every log value here (max Lv = 4*20+3 = 83 for K=2, VW=21).
    wire [7:0] La = {eA, fA};
    wire [7:0] Lb = {eB, fB};
    wire [7:0] Lc = {eC, fC};
    wire [7:0] Ld = {eD, fD};
    wire [7:0] Lv = {eV, fV};

    wire [7:0] X  = La + Lb;          // log2(A)+log2(B)
    wire [7:0] Y  = Lc + Ld;          // log2(C)+log2(D)
    wire       zx = zA | zB;          // A*B == 0
    wire       zy = zC | zD;          // C*D == 0

    // ---- LNS add: s = max(X,Y) + F(|X-Y|) ----
    wire [8:0] s;
    wire       s_zero;
    lns_add #(.LW(8)) ADD (.X(X), .Y(Y), .zx(zx), .zy(zy), .s(s), .s_zero(s_zero));

    // ---- log-domain comparison: out = s > log2(Vth) ----
    reg out_c;
    always @* begin
        if (zV)          out_c = s_zero ? 1'b0 : 1'b1;   // Vth==0 -> out=(S>0)
        else if (s_zero) out_c = 1'b0;                   // S==0, Vth>0
        else             out_c = (s > Lv) ? 1'b1 : 1'b0;
    end

    // ---- registered output ----
    always @(posedge clk) out <= out_c;
endmodule
`default_nettype wire
