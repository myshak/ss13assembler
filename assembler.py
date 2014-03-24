#!/usr/bin/python

import re
import sys
import os

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

RE_MNEMONIC         =   re.compile("^(" + "|".join([x[0] for x in MNEMONICS]) + ")\s+(-?\d|" + LABEL_IDENTIFIER + ")?$")
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

def usage():
  print "Usage: assembler.py input.asm"

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
  
def emit(ctx, mnemonic, args):
  # Convert arguments to a hex char
  args = [hex(int(x))[2:].upper() for x in args]
  debug_print(ctx, "Emiting %s %s" %(mnemonic, args), ctx.orig_line)
  
  ctx.bytecode.append(mnemonic[1] + ''.join(args))

def handle_jump(ctx, mnemonic, args):
  debug_print(ctx, "Handling jump", ctx.orig_line)
  
  if len(args) != 1:
    print_error(ctx, "Unexpected number of arguments for mnemonic '%s': expected %s got %s" % ( mnemonic[0], m[2], len(args) ))
    return
  
  arg = args[0]
  
  if RE_LABEL_IDENTIFIER.match(arg):
    if arg not in ctx.labels:
      print_error(ctx, "Label '%s' was not delcared" % ( arg ))
      return
    
    label = ctx.labels[arg]

    jump_len = label[1] - ctx.cur_instruction
    if jump_len == 0:
      # Ignore the JMP instruction
      print_warning(ctx, "Jump of zero length, ignoring")
      ctx.cur_instruction -= 1
      return
    if abs(jump_len) > 32:
      print_error(ctx, "Jump to label '%s' is too long: jump length is %s, but the max is 32" % ( arg, jump_len ))
      return
    # The arithmetic supports jumping by 4 addresses only
    if abs(jump_len) not in  range(4,32,4):
      print_error(ctx, "Distance to label '%s' is not a multiple of 4: distance is %s which is not in %s" % ( arg, abs(jump_len), repr(range(4,33,4)) ))
      return
    
    #JMP  x <  8:  pc -= 4*(x+1)
    #     x >= 8:  pc += 4*(x-7)
    if jump_len < 0:
      # Jump backward
      jump_val = (abs(jump_len)/4)-1
      emit(ctx, mnemonic, [jump_val])
    else:
      # Jump forward
      jump_val = (abs(jump_len)/4)+7
      emit(ctx, mnemonic, [jump_val])
  else:
    try:
      jump_val = int(arg)
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
  m = [x for x in MNEMONICS if x[0] == mnemonic][0]
  args = "".join(arg.split())
  args = args.split(',')
  
  # Check for arguments in an argumentless mnemonic
  if m[2] == 0 and args:
    print_error(ctx, "Unexpected argument(s) '%s' for argumentless mnemonic '%s'" % ( arg, mnemonic ))
    return
  # Check for incorrect amount of arguments
  if m[2] != len(args):
    print_error(ctx, "Unexpected number of arguments for mnemonic '%s': expected %s got %s" % ( mnemonic, m[2], len(args) ))
    return
  # Check for correct range of arguments. Works for us, because all arguments are 4 bit numbers
  if mnemonic == "JMP":
    handle_jump(ctx, m, args)
  else:
    for i in args:
      try:
        if not (0 <= int(i) <= 15):
          print_error(ctx, "Argument out of range: 0 <= %s <= 15" % ( i ))
          return
      except ValueError:
        print_error(ctx, "Argument not an integer: '%s'" % ( i ))
        return
    
    emit(ctx, m, args)
    
  ctx.cur_instruction += 1

      
  
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
            debug_print(ctx, "Skipping next instruction", line)
            continue
          handle_mnemonic(ctx, is_mnemonic.group(1), is_mnemonic.group(2))
          if ctx.error:
            return
          continue
        
        print_error(ctx, "Syntax error:")
        return
          
    print "Output bytecode: "
    print ' '.join(ctx.bytecode)
          
  except EnvironmentError, e:
    print e

def main(argv):
  if len(argv) < 2:
    usage()
    return 0
  
  parse(argv[1])

  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))