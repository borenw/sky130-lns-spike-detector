// tb_vthp.v -- checks rtl/vth_prime.v against the golden model (verif/vthp_vec.csv).
`default_nettype none
`timescale 1ns/1ps
module tb_vthp;
    localparam integer MAXV = 300000;
    reg [9:0] Cc[0:MAXV-1], Dd[0:MAXV-1], Vv[0:MAXV-1];
    reg [5:0] Ee[0:MAXV-1];
    integer   NV;

    reg  [9:0] C, D, Vth;
    wire [5:0] Vthp;
    vth_prime #(.WIDTH(10), .K(2)) DUT (.C(C), .D(D), .Vth(Vth), .Vthp(Vthp));

    integer fi, i, r, cc, dd, vv, ee, fails;
    reg [1023:0] line;
    initial begin
        fi = $fopen("verif/vthp_vec.csv", "r");
        if (fi == 0) begin $display("FATAL: no verif/vthp_vec.csv"); $finish; end
        r = $fgets(line, fi);                                   // header
        i = 0;
        while (!$feof(fi)) begin
            r = $fgets(line, fi);
            if (r > 0) begin
                r = $sscanf(line, "%d,%d,%d,%d", cc, dd, vv, ee);
                if (r == 4) begin
                    Cc[i]=cc[9:0]; Dd[i]=dd[9:0]; Vv[i]=vv[9:0]; Ee[i]=ee[5:0]; i=i+1;
                end
            end
        end
        $fclose(fi); NV = i; fails = 0;
        for (i = 0; i < NV; i = i + 1) begin
            C = Cc[i]; D = Dd[i]; Vth = Vv[i];
            #1;
            if (Vthp !== Ee[i]) begin
                fails = fails + 1;
                if (fails <= 10)
                    $display("MISMATCH C=%0d D=%0d Vth=%0d got=%0d exp=%0d",
                             Cc[i], Dd[i], Vv[i], Vthp, Ee[i]);
            end
        end
        $display("vth_prime: %0d vectors, %0d mismatches", NV, fails);
        if (fails == 0) $display("RESULT: PASS"); else $display("RESULT: FAIL");
        $finish;
    end
endmodule
`default_nettype wire
