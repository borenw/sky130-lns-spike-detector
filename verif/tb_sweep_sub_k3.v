// SUBTRACTION Vth sweep over several operand sets.  Drives BOTH designs (classic
// mult_sub vs multiplier-free log_sub) from RTL and records each registered 1-bit
// output.  Reads verif/sweep_sub_vec.csv (sid,A,B,C,D,Vth) -> verif/sweep_sub_rtl_k3.csv.
`default_nettype none
`timescale 1ns/1ps
module tb_sweep_sub;
    localparam integer MAXV = 8000;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg [3:0]  Sid[0:MAXV-1];
    reg [9:0]  Aa[0:MAXV-1], Bb[0:MAXV-1], Cc[0:MAXV-1], Dd[0:MAXV-1];
    reg [20:0] Vv[0:MAXV-1];
    integer    NV;

    reg  [9:0]  A, B, C, D;
    reg  [20:0] Vth;
    wire        out_m, out_l;

    mult_sub #(.WIDTH(10), .VW(21)) M (
        .clk(clk), .A(A), .B(B), .C(C), .D(D), .Vth(Vth), .out(out_m));
    log_sub  #(.WIDTH(10), .K(3), .VW(21)) L (
        .clk(clk), .A(A), .B(B), .C(C), .D(D), .Vth(Vth), .out(out_l));

    integer fi, fo, r, i, n;
    reg [1023:0] line;
    integer sid, a, b, c, d, vth;

    initial begin
        fi = $fopen("verif/sweep_sub_vec.csv", "r");
        if (fi == 0) begin $display("FATAL: no verif/sweep_sub_vec.csv"); $finish; end
        r = $fgets(line, fi);                             // header
        i = 0;
        while (!$feof(fi)) begin
            r = $fgets(line, fi);
            if (r > 0) begin
                n = $sscanf(line, "%d,%d,%d,%d,%d,%d", sid, a, b, c, d, vth);
                if (n == 6) begin
                    Sid[i]=sid[3:0]; Aa[i]=a[9:0]; Bb[i]=b[9:0]; Cc[i]=c[9:0]; Dd[i]=d[9:0];
                    Vv[i]=vth[20:0]; i = i + 1;
                end
            end
        end
        $fclose(fi);
        NV = i;

        fo = $fopen("verif/sweep_sub_rtl_k3.csv", "w");
        $fwrite(fo, "sid,A,B,C,D,Vth,out_mult,out_log\n");
        for (i = 0; i < NV; i = i + 1) begin
            A = Aa[i]; B = Bb[i]; C = Cc[i]; D = Dd[i]; Vth = Vv[i];
            repeat (3) @(posedge clk);
            #1;
            $fwrite(fo, "%0d,%0d,%0d,%0d,%0d,%0d,%0b,%0b\n",
                    Sid[i], Aa[i], Bb[i], Cc[i], Dd[i], Vv[i], out_m, out_l);
        end
        $fclose(fo);
        $display("SUB SWEEP DONE: %0d points -> verif/sweep_sub_rtl_k3.csv", NV);
        $finish;
    end
endmodule
`default_nettype wire
