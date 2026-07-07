set sdc_version 2.0
current_design vth_prime
create_clock -name vclk -period 5000.0
set_input_delay  500 -clock vclk [all_inputs]
set_output_delay 500 -clock vclk [all_outputs]
set_max_delay 4000 -from [all_inputs] -to [all_outputs]
