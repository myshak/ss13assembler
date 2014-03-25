#00 50 A0 B0 30 C0 11 81

NOP
label:
  OR 0 #foo?
  IEN 0 #barbar
  OEN 0
  AND 0
label2:
  JMP label
  LD 1
  STO 1
    #dd
