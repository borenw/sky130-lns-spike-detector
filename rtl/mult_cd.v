// mult_cd.v -- plain unsigned 10x10 multiplier: the multiplier-based counterpart to the
// log-domain (log2 C + log2 D) combine.  Same 10-bit C, D inputs as vth_prime.
`default_nettype none
module mult_cd (input wire [9:0] C, D, output wire [19:0] P);
    assign P = C * D;
endmodule
`default_nettype wire
