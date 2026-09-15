; sample fixture for tests - not a real print
; part footprint X 40..80, Y 20..80 (first XY move is a travel, so the origin is
; not part of the printed extent); the pocket at X60 with the default +30 mm
; tool offset puts the nozzle at X30 - outside the part, so the insert is legal
M104 S200
M140 S60
G28
G90
M82
;LAYER:0
G1 Z0.2 F1200
G0 X40 Y20 F1500
G1 X80 Y20 E2.0
;LAYER:1
G1 Z2.0
G1 X80 Y80 E3.0
;LAYER:2
G1 Z4.0
G1 X40 Y80 E4.0
;LAYER:3
G1 Z6.0
G1 X60 Y60 E4.5
;MAGNET_INSERT X60 Y60 Z6 S+X
G1 X40 Y20 E5.0
;LAYER:4
G1 Z8.0
G1 X80 Y80 E6.0
M104 S0
M140 S0
