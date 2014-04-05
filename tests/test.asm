#00 50 A0 B0 30 C0 11 81

NOP
  OR 0 #foo?
label:
  IEN 0 #barbar
  RTN
  OEN 0
  AND 15
label2:
  JMP label
  LD 1
  STO 1
    #dd
