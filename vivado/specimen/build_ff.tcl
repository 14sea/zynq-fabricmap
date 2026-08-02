# Build one clb_ff_config specimen family.
#
# The FF's INIT is a cell property, so the LUT-INIT trick applies: place and route
# ONCE, then re-write the bitstream per INIT value.  That gives a perfectly isolated
# diff for the per-FF bits.  Control-set variants (USE_CE / USE_R) change the netlist
# and therefore need their own implementation run — they are separate invocations.
#
#   vivado -mode batch -source build_ff.tcl -tclargs <outdir> <site> <ffbel> <use_ce> <use_r> <init 0|1>...
set outdir [lindex $argv 0]
set site   [lindex $argv 1]
set ffbel  [lindex $argv 2]
set usece  [lindex $argv 3]
set user   [lindex $argv 4]
set inits  [lrange $argv 5 end]

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
set lutbel [string index $ffbel 0]6LUT
file mkdir $outdir

create_project -in_memory -part $part
read_verilog $here/specimen_ff.v
synth_design -top specimen_ff -part $part -flatten_hierarchy none \
             -generic USE_CE=$usece -generic USE_R=$user

set pins {A20 B19 B20 C20 D18 D19}
for {set k 0} {$k < 6} {incr k} {
    set_property PACKAGE_PIN [lindex $pins $k] [get_ports i[$k]]
}
set_property PACKAGE_PIN D20 [get_ports o]
set_property PACKAGE_PIN E17 [get_ports q]
set_property PACKAGE_PIN E18 [get_ports clk]
set_property PACKAGE_PIN E19 [get_ports ce]
set_property PACKAGE_PIN F16 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports *]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets -of_objects [get_pins bufg_inst/I]]

set lut [get_cells target]
set ff  [get_cells ff]
set_property LOC $site $lut
set_property BEL $lutbel $lut
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $lut
set_property LOC $site $ff
set_property BEL $ffbel $ff

place_design
route_design
write_checkpoint -force $outdir/base.dcp

set fh [open $outdir/placement.json w]
puts $fh "{"
puts $fh "  \"part\": \"$part\","
puts $fh "  \"vivado_version\": \"[version -short]\","
puts $fh "  \"requested_site\": \"$site\","
puts $fh "  \"requested_bel\": \"$lutbel+$ffbel\","
puts $fh "  \"resolved_loc\": \"[get_property LOC $lut]\","
puts $fh "  \"resolved_bel\": \"[get_property BEL $lut]\","
puts $fh "  \"ff_loc\": \"[get_property LOC $ff]\","
puts $fh "  \"ff_bel\": \"[get_property BEL $ff]\","
puts $fh "  \"ff_ref\": \"[get_property REF_NAME $ff]\","
puts $fh "  \"ff_init\": \"[get_property INIT $ff]\","
puts $fh "  \"ff_ce_net\": \"[get_nets -quiet -of_objects [get_pins ff/CE]]\","
puts $fh "  \"ff_r_net\": \"[get_nets -quiet -of_objects [get_pins ff/R]]\","
puts $fh "  \"use_ce\": \"$usece\","
puts $fh "  \"use_r\": \"$user\","
puts $fh "  \"lock_pins\": \"[get_property LOCK_PINS $lut]\","
puts $fh "  \"tile\": \"[get_tiles -of_objects [get_sites $site]]\","
puts $fh "  \"pin_mapping\": {"
set sep ""
foreach pin {I0 I1 I2 I3 I4 I5} {
    puts $fh "$sep    \"$pin\": \"[get_bel_pins -quiet -of_objects [get_pins target/$pin]]\""
    set sep ","
}
puts $fh "  },"
puts $fh "  \"variants\": \"$inits\""
puts $fh "}"
close $fh

# INIT values arrive as plain 0/1 on the command line and are formed here: passing
# 1'b0 through a shell would need quoting that is easy to get wrong, and it silently
# merged two arguments into one on the first attempt.
foreach init $inits {
    set_property INIT 1'b$init $ff
    write_bitstream -force $outdir/spec_init$init.bit
    puts "SPECIMEN_VARIANT init=$init resolved_init=[get_property INIT $ff]"
}
puts "SPECIMEN_DONE"
