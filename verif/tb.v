// One testbench, both designs.  Streams verif/vectors.csv through mult_detector
// (checked vs exp_exact) and log_detector (checked vs exp_k1) in lock-step.
// Both DUTs have 2-cycle registered-I/O latency: a vector driven at negedge i is
// observed at the outputs at negedge i+2.
`default_nettype none
`timescale 1ns/1ps
module tb;
    localparam integer MAXV = 200000;

    reg          clk = 1'b0;
    always #5 clk = ~clk;

    // stimulus / expected storage
    reg  [9:0]  Aa[0:MAXV-1], Bb[0:MAXV-1], Cc[0:MAXV-1], Dd[0:MAXV-1];
    reg  [20:0] Vv[0:MAXV-1];
    reg         Ee[0:MAXV-1];      // exp_exact
    reg         Ek[0:MAXV-1];      // exp_k1
    integer     NV;

    // driven inputs
    reg  [9:0]  A, B, C, D;
    reg  [20:0] Vth;

    // DUT outputs
    wire out1, out2;

    mult_detector #(.WIDTH(10), .VW(21)) DUT1 (
        .clk(clk), .A(A), .B(B), .C(C), .D(D), .Vth(Vth), .out(out1));
    log_detector  #(.WIDTH(10), .K(2), .VW(21)) DUT2 (
        .clk(clk), .A(A), .B(B), .C(C), .D(D), .Vth(Vth), .out(out2));

    integer fd, r, n, i, k;
    integer err1, err2;
    reg [1023:0] line;
    integer a, b, c, d, vth, ee, ek;

    initial begin
        // ---- load vectors ----
        fd = $fopen("verif/vectors.csv", "r");
        if (fd == 0) begin $display("FATAL: cannot open verif/vectors.csv"); $finish; end
        r = $fgets(line, fd);                       // header line, discard
        i = 0;
        while (!$feof(fd)) begin
            r = $fgets(line, fd);
            if (r > 0) begin
                n = $sscanf(line, "%d,%d,%d,%d,%d,%d,%d", a, b, c, d, vth, ee, ek);
                if (n == 7) begin
                    Aa[i]=a[9:0]; Bb[i]=b[9:0]; Cc[i]=c[9:0]; Dd[i]=d[9:0];
                    Vv[i]=vth[20:0]; Ee[i]=ee[0]; Ek[i]=ek[0];
                    i = i + 1;
                end
            end
        end
        $fclose(fd);
        NV = i;
        $display("TB: loaded %0d vectors from verif/vectors.csv", NV);

        // ---- drive & check ----
        err1 = 0; err2 = 0;
        A=0; B=0; C=0; D=0; Vth=0;
        for (i = 0; i <= NV+1; i = i + 1) begin
            @(negedge clk);
            if (i < NV) begin
                A <= Aa[i]; B <= Bb[i]; C <= Cc[i]; D <= Dd[i]; Vth <= Vv[i];
            end
            if (i >= 2) begin                        // output now reflects vector i-2
                k = i - 2;
                if (out1 !== Ee[k]) begin
                    err1 = err1 + 1;
                    if (err1 <= 10)
                        $display("  D1 MISMATCH vec %0d A=%0d B=%0d C=%0d D=%0d Vth=%0d  got=%b exp_exact=%b",
                                 k, Aa[k],Bb[k],Cc[k],Dd[k],Vv[k], out1, Ee[k]);
                end
                if (out2 !== Ek[k]) begin
                    err2 = err2 + 1;
                    if (err2 <= 10)
                        $display("  D2 MISMATCH vec %0d A=%0d B=%0d C=%0d D=%0d Vth=%0d  got=%b exp_k1=%b",
                                 k, Aa[k],Bb[k],Cc[k],Dd[k],Vv[k], out2, Ek[k]);
                end
            end
        end

        // ---- summary ----
        $display("");
        $display("=========================================================");
        $display(" VERIFICATION SUMMARY  (%0d vectors)", NV);
        $display("  Design 1 (mult_detector) vs exp_exact : %0d mismatches  -> %s",
                 err1, (err1==0) ? "PASS" : "FAIL");
        $display("  Design 2 (log_detector)  vs exp_k1    : %0d mismatches  -> %s",
                 err2, (err2==0) ? "PASS" : "FAIL");
        if (err1==0 && err2==0)
            $display(" RESULT: PASS  (both designs bit-exact to their golden model)");
        else
            $display(" RESULT: FAIL");
        $display("=========================================================");
        $finish;
    end
endmodule
`default_nettype wire
