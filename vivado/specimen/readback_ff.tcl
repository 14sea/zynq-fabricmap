# Read back the netlist edge a mux specimen actually contains, from its routed
# checkpoint.  The build script recorded the FF's own D bel-pin, which says nothing
# about where the data comes from — it is the same string in every variant.  What
# member_identity claims is that Vivado built a particular EDGE, so the evidence has to
# be the driver of that net.
#
#   vivado -mode batch -source readback_ff.tcl -tclargs <dir-with-base.dcp>
set dir [lindex $argv 0]
open_checkpoint $dir/base.dcp

set ff  [get_cells ff]
set lut [get_cells target]
set dpin [get_pins ff/D]
set dnet [get_nets -quiet -of_objects $dpin]
set drv  [get_pins -quiet -of_objects $dnet -filter {DIRECTION == OUT}]
set drvcell ""
set drvref ""
set srcport ""
set srcpin ""
if {$drv ne ""} {
    set drvcell [get_property PARENT_CELL [lindex $drv 0]]
    if {$drvcell eq ""} { set drvcell [regsub {/[^/]+$} [lindex $drv 0] ""] }
    set drvref [get_property REF_NAME [get_cells -quiet $drvcell]]
    # Trace one step further back so the bypass variant can be proved POSITIVELY: an
    # IBUF is only meaningful evidence if it is fed by a top-level port on a known
    # package pin.  "not a LUT6" would be satisfied by anything at all.
    set innet [get_nets -quiet -of_objects [get_pins -quiet $drvcell/I]]
    if {$innet ne ""} {
        set srcport [get_ports -quiet -of_objects $innet]
        if {$srcport ne ""} {
            set srcpin [get_property -quiet PACKAGE_PIN [lindex $srcport 0]]
        }
    }
}

set fh [open $dir/ff_readback.json w]
puts $fh "{"
puts $fh "  \"ff_loc\": \"[get_property LOC $ff]\","
puts $fh "  \"ff_bel\": \"[get_property BEL $ff]\","
puts $fh "  \"lut_bel\": \"[get_property BEL $lut]\","
puts $fh "  \"ff_d_bel_pin\": \"[get_bel_pins -quiet -of_objects $dpin]\","
puts $fh "  \"ff_d_net\": \"$dnet\","
puts $fh "  \"ff_d_net_route_status\": \"[get_property -quiet ROUTE_STATUS $dnet]\","
puts $fh "  \"ff_d_driver_pin\": \"$drv\","
puts $fh "  \"ff_d_driver_cell\": \"$drvcell\","
puts $fh "  \"ff_d_driver_ref\": \"$drvref\","
puts $fh "  \"ff_d_source_port\": \"$srcport\","
puts $fh "  \"ff_d_source_package_pin\": \"$srcpin\","
puts $fh "  \"lut_o_net\": \"[get_nets -quiet -of_objects [get_pins target/O]]\""
puts $fh "}"
close $fh
puts "FF_READBACK_DONE $drvref $drv"
