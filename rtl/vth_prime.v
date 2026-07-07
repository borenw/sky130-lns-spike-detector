// vth_prime.v -- the "Vth′(C,D)" LUT block, as its own combinational module.
//   inputs  C, D, Vth  (all WIDTH-bit)      output  Vthp  (quarter-log2 units)
//
//   g       = log2(Vth) - log2(C*D)
//   Vth′    = log2(1 + 2^g) = max(0,g) + F(|g|),   F(d) = log2(1 + 2^-d)   (F-ROM)
//
// Three identical K-bit log2 converters (C, D, Vth), an adder for log2(C*D),
// a subtract/abs for |g|, a relu for max(0,g), the F-ROM, and a final adder.
// Reuses rtl/lod5.v and rtl/lns_ftable.v unchanged.  Values are in 1/2^K-log2 units.
`default_nettype none
module vth_prime #(
    parameter WIDTH = 10,
    parameter K     = 2
) (
    input  wire [WIDTH-1:0] C, D, Vth,
    output wire [5:0]       Vthp        // max(0,g)+F(|g|) <= 39+4 = 43, fits 6 bits
);
    localparam EW = $clog2(WIDTH);                 // exponent bits (4 for WIDTH=10)

    // ---- three K-bit log2 converters ----
    wire [EW-1:0] eC, eD, eV;
    wire [K-1:0]  fC, fD, fV;
    wire          zC, zD, zV;
    lod #(.N(WIDTH), .FR(K)) LC (.v(C),   .e(eC), .frac(fC), .is_zero(zC));
    lod #(.N(WIDTH), .FR(K)) LD (.v(D),   .e(eD), .frac(fD), .is_zero(zD));
    lod #(.N(WIDTH), .FR(K)) LV (.v(Vth), .e(eV), .frac(fV), .is_zero(zV));

    // L(v) = (e<<K)+frac = {e,frac}   (quarter-log2 units for K=2)
    wire [EW+K-1:0] Lc  = {eC, fC};                // log2(C)
    wire [EW+K-1:0] Ld  = {eD, fD};                // log2(D)
    wire [EW+K-1:0] Lv  = {eV, fV};                // log2(Vth)
    wire [EW+K:0]   Lcd = Lc + Ld;                 // log2(C*D)

    // gap g = log2(Vth) - log2(C*D);  address d = |g|;  relu = max(0,g)
    wire       gpos = (Lv > Lcd);
    wire [7:0] d    = gpos ? (Lv - Lcd) : (Lcd - Lv);
    wire [7:0] relu = gpos ? (Lv - Lcd) : 8'd0;

    // F(|g|) correction ROM
    wire [3:0] Fd;
    lns_ftable FT (.d(d), .f(Fd));

    // full-exact Vth′ = max(0,g) + F(|g|)
    assign Vthp = relu + Fd;
endmodule
`default_nettype wire
