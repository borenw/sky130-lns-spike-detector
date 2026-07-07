// Vth sweep at fixed A,B,C,D = 25,30,12,40.  Drives BOTH designs from RTL and records
// the registered comparator output of each vs Vth.  Output: verif/sweep_rtl.csv.
`default_nettype none
`timescale 1ns/1ps
module tb_sweep;
    localparam integer MAXV = 8000;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg [20:0] Vs[0:MAXV-1];
    integer    NV;

    reg  [9:0]  A, B, C, D;
    reg  [20:0] Vth;
    wire        out_m, out_l;          // classic multiplier vs log/LNS

    mult_detector #(.WIDTH(10), .VW(21)) M (
        .clk(clk), .A(A), .B(B), .C(C), .D(D), .Vth(Vth), .out(out_m));
    log_detector  #(.WIDTH(10), .K(2), .VW(21)) L (
        .clk(clk), .A(A), .B(B), .C(C), .D(D), .Vth(Vth), .out(out_l));

    integer fi, fo, r, i, v;
    reg [1023:0] line;

    initial begin
        fi = $fopen("verif/sweep_vth.txt", "r");
        if (fi == 0) begin $display("FATAL: no verif/sweep_vth.txt"); $finish; end
        i = 0;
        while (!$feof(fi)) begin
            r = $fgets(line, fi);
            if (r > 0) begin
                r = $sscanf(line, "%d", v);
                if (r == 1) begin Vs[i] = v[20:0]; i = i + 1; end
            end
        end
        $fclose(fi);
        NV = i;

        fo = $fopen("verif/sweep_rtl.csv", "w");
        $fwrite(fo, "Vth,out_mult,out_log\n");

        A = 10'd25; B = 10'd30; C = 10'd12; D = 10'd40;   // fixed operands
        Vth = 21'd0;
        // hold each Vth long enough to flush the 2-cycle pipeline, then sample
        for (i = 0; i < NV; i = i + 1) begin
            Vth = Vs[i];
            repeat (3) @(posedge clk);
            #1;
            $fwrite(fo, "%0d,%0b,%0b\n", Vs[i], out_m, out_l);
        end
        $fclose(fo);
        $display("SWEEP DONE: %0d points (A·B+C·D=%0d) -> verif/sweep_rtl.csv",
                 NV, 25*30 + 12*40);
        $finish;
    end
endmodule
`default_nettype wire
