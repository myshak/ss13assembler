#!/usr/bin/python
#
# SS13 LLJK MC14500B Assembler
# Copyright (C) 2014 mysha (mysha@mysha.cu.cc) 
# License: http://www.gnu.org/licenses/gpl.html GPL version 3 or higher

import re
import sys

MNEMONICS           =   [
  # Mnemonic, opcode, argument count
  ("NOP",   "0", 0),
  ("LD",    "1", 1),
  ("LDC",   "2", 1),
  ("AND",   "3", 1),
  ("ANDC",  "4", 1),
  ("OR",    "5", 1),
  ("ORC",   "6", 1),
  ("XNOR",  "7", 1),
  ("STO",   "8", 1),
  ("STOC",  "9", 1),
  ("IEN",   "A", 1),
  ("OEN",   "B", 1),
  ("JMP",   "C", 1),
  ("RTN",   "D", 0),
  ("SKZ",   "E", 0),
#  ("NOP",    "F", 1),
  ]

DEBUG = False

LABEL_IDENTIFIER    =   "[a-zA-Z]\w*"
LABEL               =   "(" + LABEL_IDENTIFIER + "):"
COMMENT             =   "#.*$"

RE_MNEMONIC         =   re.compile("^(" + "|".join([x[0] for x in MNEMONICS]) + ")" + 
                                   "(?:\s+(-?\d+|" + LABEL_IDENTIFIER + "))?$", re.I)
RE_LABEL_IDENTIFIER =   re.compile("^" + LABEL_IDENTIFIER + "$")
RE_LABEL            =   re.compile("^" + LABEL + "$")
RE_COMMENT          =   re.compile(COMMENT)

class context:
  def __init__(self, filename):
    self.filename = filename
    self.cur_line = 0
    self.cur_instruction = 0
    self.skip_next = False
    self.labels = {} # (name, instruction_pos, line_pos)
    self.bytecode = []
    self.error = False
    self.orig_line = ""

def usage(executable):
  print "Usage: %s <file>" % executable

def debug_print(ctx, stmt, line):
  if DEBUG:
    print "%s:%s: debug: %s:\t\t\t%s" % (ctx.filename, ctx.cur_line, stmt, line.strip('\n'))
  
def print_error(ctx, error):
  print "%s:%s: error: %s" % (ctx.filename, ctx.cur_line, error)
  print ctx.orig_line    
  ctx.error = True

def print_warning(ctx, warn):
  print "%s:%s: warning: %s" % (ctx.filename, ctx.cur_line, warn)
  print ctx.orig_line    
  
def to_hexstring(num):
  val = ""
  if isinstance(num, str):
    val = int(num, 10)
  else:
    val = num
  return hex(val)[2:].upper()
  
def emit(ctx, mnemonic, arg):
  # Convert arguments to a hex char
  args = []
  for i in arg:
    if isinstance(i, str) or isinstance(i,int):
      # Bare value
      args.append(to_hexstring(i))
    else:
      # Deffered parameter
      # Tuple of ("Instruction", param1, param2)
      args.append(i)
  debug_print(ctx, "Emiting %s %s" %(mnemonic, args), ctx.orig_line)
  
  # We need a full byte (opcode + argument), if none supplied, add a 0
  if not args:
    args = ["0"]
  ctx.bytecode.append(mnemonic[1])
  ctx.bytecode.extend(args)

def compute_jump(ctx, label_name, target_instr):
  debug_print(ctx, "Computing jump to label '%s'" % label_name, "")
  
  if label_name not in ctx.labels:
    print_error(ctx, "Label '%s' was not delcared" % ( label_name ))
    return None

  label = ctx.labels[label_name]
  
  jump_len = label[1] - target_instr
  if jump_len == 0:
    # Ignore the JMP instruction
    print_warning(ctx, "Jump of zero length, ignoring")
    return None
  if abs(jump_len) > 32:
    print_error(ctx, "Jump to label '%s' is too long: jump length is %s, but the max is 32" % ( label_name, jump_len ))
    return None
  # The arithmetic supports jumping by 4 addresses only
  if abs(jump_len) not in  range(4,32,4):
    print_error(ctx, "Distance to label '%s' is not a multiple of 4: distance is %s which is not in %s" % ( label_name, abs(jump_len), repr(range(4,33,4)) ))
    return None
  
  jump_val = None
  #JMP  x <  8:  pc -= 4*(x+1)
  #     x >= 8:  pc += 4*(x-7)
  if jump_len < 0:
    # Jump backward
    jump_val = (abs(jump_len)/4)-1
    #emit(ctx, mnemonic, [jump_val])
  else:
    # Jump forward
    jump_val = (abs(jump_len)/4)+7
    #emit(ctx, mnemonic, [jump_val])
  return jump_val

def handle_jump(ctx, mnemonic, args):
  debug_print(ctx, "Handling jump", ctx.orig_line)
  
  if len(args) != 1:
    print_error(ctx, "Unexpected number of arguments for mnemonic '%s': expected %s got %s" % ( mnemonic[0], m[2], len(args) ))
    return
  
  arg = args[0]
  
  if RE_LABEL_IDENTIFIER.match(arg):
    # Label
    if arg not in ctx.labels:
      # Defer computing jump until we are building the bytecode
      debug_print(ctx, "Deferring jump from instruction %s to label '%s'" % (ctx.cur_instruction, arg), ctx.orig_line)
      emit(ctx, mnemonic, [("JMP", arg, ctx.cur_instruction)])
      return
    else:
      jump_val = compute_jump(ctx, arg, ctx.cur_instruction)
      if jump_val == None and not ctx.error:
        # Ignoring jump
        ctx.cur_instruction -= 1
        return
      elif jump_val == None and ctx.error:
        return
      
      emit(ctx, mnemonic, [jump_val])
  else:
    # Value
    try:
      jump_val = int(arg, 10)
      if not (0 <= jump_val <= 15):
        print_error(ctx, "Argument out of range: 0 <= %s <= 15" % ( jump_val ))
        return
      emit(ctx, mnemonic, [jump_val])
    except ValueError:
      print_error(ctx, "Argument not an integer: '%s'" % ( i ))
      return
    
  
def handle_mnemonic(ctx, mnemonic, arg):
  debug_print(ctx, "Handling mnemonic %s" % mnemonic, ctx.orig_line)
  # Grab the matching mnemonic
  # TODO: maybe make it a dict?
  m = [x for x in MNEMONICS if x[0] == mnemonic.upper()][0]
  if arg:
    # Remove whitespace between arguments
    args = "".join(arg.split()).split(',')
  else:
    args = []
    
  # Jumps are calculated after the instruction counter is increased
  ctx.cur_instruction += 1
  
  # Check for arguments in an argumentless mnemonic
  if m[2] == 0 and args:
    print_error(ctx, "Unexpected argument(s) '%s' for argumentless mnemonic '%s'" % ( arg, mnemonic ))
    return
  # Check for incorrect amount of arguments
  if m[2] != len(args):
    print_error(ctx, "Unexpected number of arguments for mnemonic '%s': expected %s got %s" % ( mnemonic, m[2], len(args) ))
    return
  if mnemonic.upper() == "JMP":
    handle_jump(ctx, m, args)
  elif mnemonic.upper() == "RTN":
    # RTN skips next instruction. Just ignore it and the next instruction
    # Offsets to labels will be different then those in the source, so give a warning
    print_warning(ctx, "Mnemonic RTN used, ignoring it and the following instruction. Offsets may be different for non-label JMP instructions")
    ctx.skip_next = True
    return
  else:
    # Check for correct range of arguments. Works for us, because all arguments are 4 bit numbers
    for i in args:
      try:
        if not (0 <= int(i, 10) <= 15):
          print_error(ctx, "Argument out of range: 0 <= %s <= 15" % ( i ))
          return
      except ValueError:
        print_error(ctx, "Argument not an integer: '%s'" % ( i ))
        return
    
    emit(ctx, m, args)

   # Jumps are calculated before the instruction counter is increased
   # ctx.cur_instruction += 1

      
  
def parse(filename):
  
  ctx = context(filename)

  try:
    with open(filename) as in_file:
      for line in in_file.readlines():
        ctx.cur_line += 1
        ctx.orig_line = line
        
        # Strip comments
        line = RE_COMMENT.sub('', line)
        
        # Strip whitespace
        line = line.strip()
              
        # Skip empty lines
        if line == "":
          continue
        
        is_label = RE_LABEL.match(line)
        if is_label:
          label_name = is_label.group(1)
          if label_name in ctx.labels:
            print_error(ctx, "Duplicate label '%s', preverious declaration at %s:%s" % (label_name, ctx.filename, ctx.labels[label_name][2]))
            return
          # Add a label for the instruction that is next
          debug_print(ctx, "Adding label for instruction %s" % ctx.cur_instruction, line)
          ctx.labels[label_name] = (label_name, ctx.cur_instruction, ctx.cur_line)
          continue
        
        is_mnemonic = RE_MNEMONIC.match(line)
        if is_mnemonic:
          debug_print(ctx, "Parsing mnemonic", line)
          if ctx.skip_next == True:
            ctx.skip_next = False
            debug_print(ctx, "Skipping next instruction", line)
            continue
          handle_mnemonic(ctx, is_mnemonic.group(1), is_mnemonic.group(2))
          if ctx.error:
            return
          continue
        
        print_error(ctx, "Syntax error:")
        return

    bytecode = []
    for i in ctx.bytecode:
      if isinstance(i, str):
        bytecode.append(i)
      elif isinstance(i, tuple):
        # Resolve deferred parameters
        if i[0] == "JMP":
          jump_val = compute_jump(ctx, i[1], i[2])
          if jump_val == None and not ctx.error:
            # Ignoring jump
            bytecode.pop()
          elif jump_val == None and ctx.error:
            return
          else:
            bytecode.append(to_hexstring(jump_val))
      else:
        print "Error while building bytecode: '%s' not recognized" % repr(i)
        
    print "Output bytecode: "
    print ' '.join([i+j for i,j in zip(bytecode[::2],bytecode[1::2])])
          
  except EnvironmentError, e:
    print e

def main(argv):
  if len(argv) < 2:
    usage(argv[0])
    return 0
  
  parse(argv[1])

  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))
