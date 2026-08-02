# Build one clb_mux specimen variant.  One implementation run per variant, because a
# mux selection is structural — see specimen_mux.v.
#
#   vivado -mode batch -source build_mux.tcl -tclargs <outdir> <site> <ffsrc> [ff_bel]
set outdir [lindex $argv 0]
set site   [lindex $argv 1]
set ffsrc  [lindex $argv 2]
set ffbel  [lindex $argv 3]
if {$ffbel eq ""} { set ffbel AFF }
# The LUT must sit in the same slice position as the FF it feeds, or the FF's data
# would have to arrive through a different mux than the one under test.
set lutbel [string index $ffbel 0]6LUT

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
file mkdir $outdir

create_project -in_memory -part $part
read_verilog $here/specimen_mux.v
synth_design -top specimen_mux -part $part -flatten_hierarchy none \
             -generic FFSRC=$ffsrc

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
# The clock pin is not on a clock-capable IO for this package, and the specimen does
# not care: it is never run on hardware, and demoting the rule keeps the pin fixed
# rather than letting the placer move IO around between variants.
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
puts $fh "  \"lock_pins\": \"[get_property LOCK_PINS $lut]\","
puts $fh "  \"tile\": \"[get_tiles -of_objects [get_sites $site]]\","
puts $fh "  \"ff_d_source\": \"[get_bel_pins -quiet -of_objects [get_pins ff/D]]\","
puts $fh "  \"pin_mapping\": {"
set sep ""
foreach pin {I0 I1 I2 I3 I4 I5} {
    puts $fh "$sep    \"$pin\": \"[get_bel_pins -quiet -of_objects [get_pins target/$pin]]\""
    set sep ","
}
puts $fh "  },"
puts $fh "  \"variants\": \"ffsrc$ffsrc\""
puts $fh "}"
close $fh

write_bitstream -force $outdir/spec_${ffbel}_ffsrc$ffsrc.bit
puts "SPECIMEN_VARIANT bel=$ffbel ffsrc=$ffsrc"
puts "SPECIMEN_DONE"
