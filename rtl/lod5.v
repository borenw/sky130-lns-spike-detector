// Leading-one detector + K fraction bits  (K-bit log2 converter front end).
// Parameterised width N and fraction width FR (= K), so the same module serves
// the input operands and the wider Vth.  Combinational.
//   is_zero = 1                         when v == 0   (log2 undefined)
//   e       = floor(log2 v)             integer part
//   frac    = the FR mantissa bits just below the leading one (MSB first),
//             zero-filled where they fall below bit 0.
// The K-bit log value is  L = (e << FR) + frac = {e, frac}  in 1/2^FR-log2 units.
`default_nettype none
module lod #(
    parameter N  = 10,
    parameter FR = 2            // fraction bits = K
) (
    input  wire [N-1:0]            v,
    output reg  [$clog2(N)-1:0]    e,
    output reg  [FR-1:0]           frac,
    output reg                     is_zero
);
    integer i, j;
    reg found;
    always @* begin
        e       = {($clog2(N)){1'b0}};
        frac    = {FR{1'b0}};
        is_zero = 1'b1;
        found   = 1'b0;
        // priority scan from MSB: first set bit is the leading one
        for (i = N-1; i >= 0; i = i - 1) begin
            if (!found && v[i]) begin
                found   = 1'b1;
                is_zero = 1'b0;
                e       = i[$clog2(N)-1:0];
                // capture the FR bits below the leading one, MSB (bit i-1) first
                for (j = 1; j <= FR; j = j + 1)
                    frac[FR-j] = (i - j >= 0) ? v[(i - j >= 0) ? (i - j) : 0] : 1'b0;
            end
        end
    end
endmodule
`default_nettype wire
