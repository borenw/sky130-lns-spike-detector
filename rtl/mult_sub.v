// Classic baseline for the SUBTRACTION kernel:  out = (A*B - C*D) > Vth  (signed, exact).
// Registered I/O, 2-cycle latency.  Vth is an unsigned (>=0) programmable threshold.
`default_nettype none
module mult_sub #(
    parameter WIDTH = 10,
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
    wire [2*WIDTH-1:0]        p1 = Ar * Br;              // A*B
    wire [2*WIDTH-1:0]        p2 = Cr * Dr;              // C*D
    wire signed [2*WIDTH+2:0] S  = $signed({3'b0, p1}) - $signed({3'b0, p2});  // A*B - C*D
    wire signed [2*WIDTH+2:0] Vs = $signed({2'b0, Vr});                        // Vth (>=0)
    wire                      out_c = (S > Vs);
    always @(posedge clk) out <= out_c;
endmodule
`default_nettype wire
