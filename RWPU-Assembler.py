from time import time

configfile = open(".config", "r")
configlines = configfile.readlines()
# set defaults
verbosity = 2 # 0 = minimum, 1 = errors only, 2 = warnings and errors, 3 = all log messages, 4 = verbose
source = "source.rwpu"
output = "mcode.rwpumc"
consolebase = 0 # 0 = no mc printing, 1 = binary, 2 = quatric, 3 = octal, 4 = hexadecimal, 5 = base 32
for i in configlines:
    if (len(i) > 1):
        i = i.split("\n")[0]
        setting = i.split(" ")[0]
        val = i.split(" ")[1]
        if setting == "asm":
            source = val
        elif setting == "mcode":
            output = val
        elif setting == "verbosity":
            try:
                val = int(val)
            except ValueError:
                print("\033[031m\033[01mConfig file error: Verbosity value is not an integer.\033[0m")
                exit(1)
            verbosity = val
        elif setting == "consolebase":
            try:
                val = int(val)
            except ValueError:
                print("\033[031m\033[01mConfig file error: Console base value is not an integer.\033[0m")
                exit(1)
            consolebase = val
        elif not (setting == "schemfolder" or setting == "schemname" or setting == "schem" or setting == "maxline"):
            print("\033[031m\033[01mConfig file error: Unknown setting {}. Please read documentation.\033[0m".format(i))
            exit(1)

verbosity = max(0, verbosity)
try:
    f = open(source, "r")
except FileNotFoundError:
    print("\033[031m\033[01mThe specified source file ({}) was not found. Please double check your path and filename in .config file.\033[0m".format(source))
    exit(0)

start = time()

lines = f.readlines()
f.close()

f = open(output, "w")

instruction = 1 # Position of current instruction
instructionbinary = "" # Binary value for that instruction, which gets pushed to instruction list when it is done.
binaryinstlist = [] # Final binary instruction list
labelnames = [] # List of all labels
labelpos = [] # List of label positions
baseref = list("0123456789ABCDEFGHIJKLMNOPQRSTUV") # All characters for bases up to 32
line = 0 # Line, to tell the user what line to look at when an error occurs
error = 0 # Error variable, doesn't write to file or display final code result if there is a fatal error.
compilesuccess = True # If a line was compiled properly

def msg(m, level):
    formatter = ""
    global verbosity
    if level <= 1:
        formatter = "\033[031m"
    elif level == 2:
        formatter = "\033[033m"
    if level <= verbosity:
        print("{}{}\033[0m".format(formatter, m))

def format(n, l): # format integer n to have l places minimum
    n = str(n)
    while len(n) < l:
        n = "0" + n
    return n

def formatapp(n, l): # add 0 at end of string until length requirement
    n = str(n)
    while len(n) < l:
        n += "0"
    return n

def frombinary(binary, l2base): # binary to a base which is a power of 2
    if l2base == 1: # base 2
        return binary
    elif l2base < 6: # base 4, 8, 16, 32
        blist = list(binary)
        bitval = 1 << (l2base-1)
        outval = 0
        strout = ""
        for i in blist:
            newchar = True
            if i == "1":
                outval += bitval
            if bitval == 1:
                bitval = 1 << (l2base-1)
                strout += baseref[outval]
                outval = 0
                newchar = False
            else:
                bitval >>= 1
        if newchar:
            strout += baseref[outval]
        return strout
    else:
        return "[Invalid Base]"

def b2d(binary): # Binary string to decimal
    binary = list(binary)
    val = 1
    dec = 0
    for i in range(len(binary)):
        if binary[len(binary)-i-1] == "1":
            dec += val
        val <<= 1
    return dec

def d2b(integer, bits): # Integer converted to binary string to 'bits' bits
    mask = 1
    strout = ""
    for i in range(bits):
        if integer & mask == 0:
            strout = "0" + strout
        else:
            strout = "1" + strout
        mask <<= 1
    return strout

def striparg(s): # Remove first character in a string
    s = list(s)
    out = ""
    if (len(s) == 1):
        return ""
    for i in range(1, len(s)):
        out += s[i]
    return out

def checkreg(s): # Returns (errcode, strippedval)
    sl = list(s)
    if sl[0] != "r" and sl[0] != "$":
        return (1, 0) # Value is not register error
    try:
        arg = striparg(s)
        arg = int(arg)
    except ValueError:
        return (2, 0) # Register reference is not valid
    if arg < 0:
        arg = -arg
        arg = arg&15
        return (3, arg) # Argument was negative (warn)
    elif arg >= 16:
        arg = arg&15
        return (4, arg) # Argument was truncated (warn)
    else:
        return (0, arg) # Success

def checklabel(s):
    if list(s)[0] != ".":
        return (1, 0) # womp womp, it's not a label
    global labelnames, labelpos
    for i in range(len(labelnames)):
        if labelnames[i] == s:
            return (0, labelpos[i]) # Success
    return (2, 0) # Label not referenced / referenced later

def checkaddr(s):
    if list(s)[0] != "#":
        return (1, 0) # not a valid inst address prefix
    else:
        s = striparg(s)
        try:
            s = int(s)
            if s < 1:
                s = -s
                s &= 1023
                return (3, 0) # Negative address (warn)
            if s == 0:
                return (4, 0) # Zero address, set to 1 (warn)
            if s > 1023:
                return (5, s&1023) # Address too high, truncated (warn)
            return (0, s)
        except ValueError:
            return (2, 0) # Non-integer address

def checkint(s):
    try:
        s = int(s)
        if s < -128:
            s = -s
            s &= 255
            return (2, s) # Integer below range
        elif s > 255:
            s &= 255
            return (3, s) # Integer above range
        elif s < 0:
            s += 256
        return (0, s)
    except ValueError:
        return (1, 0) # Not an integer

def checkcond(s):
    s = s.lower().split("\n")[0]
    for i in ["always", "alw", "1", "true", "yes"]: # Condition 0
        if s == i:
            return (0, 0)
        
    for i in ["never", "nev", "false", "no"]: # Condition 1
        if s == i:
            return (1, 1)
    
    for i in ["zero", "z", "eq", "0", "equal"]: # Condition 2
        if s == i:
            return (0, 2)
    
    for i in ["nonzero", "nz", "!zero", "ne", "notequal", "!equal"]: # Condition 3
        if s == i:
            return (0, 3)
    
    for i in ["cout", "overflow", "of", "co", "carryout"]: # Condition 4
        if s == i:
            return (0, 4)
    
    for i in ["!cout", "nocarryout", "!carryout", "nooverflow", "nof", "!co"]: # Condition 5
        if s == i:
            return (0, 5)
    
    for i in ["negative", "neg", "!positive", "!pos", "notpos", "notpositive"]: # Condition 6
        if s == i:
            return (0, 6)
    
    for i in ["positive", "pos", "!negative", "!neg", "notneg", "notnegative"]: # Condition 7
        if s == i:
            return (0, 7)
    
    return (2, 1)

def checkline(broken, operands, linenum): # Operands: r: register, i: integer, a: absolute inst address, l: label
    operands = list(operands)
    values = []
    line = ""
    for i in broken:
        line += i
        if list(i)[-1] != "\n":
            line += " "
    global error
    if len(operands)+1 != len(broken):
        msg("SyntaxError: Expecting {} operands, got {}. (Are there trailing whitespaces?)\n{}Line {} in input file.".format(len(operands), len(broken) - 1, line, linenum), 1)
        error += 1
        for i in range(len(operands)):
            values.append(0)
        return values
    for i in range(1, len(operands) + 1):
        if operands[i-1] == "i": # Integer
            checkout = checkint(broken[i])
            if checkout[0] == 1:
                msg("ValueError: Expecting integer, got {} instead.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            elif checkout[0] == 2:
                msg("Warning: Integer {} on line {} is below -128 (Below signed 8-bit integer limit)", 2)
            elif checkout[0] == 3:
                msg("Warning: Integer {} on line {} is above 255 (Above unsigned 8-bit integer limit)", 2)
            else:
                msg("Operand integer value good", 4)
            values.append(checkout[1])
        elif operands[i-1] == "r": # Register
            checkout = checkreg(broken[i])
            if checkout[0] == 1:
                msg("ValueError: Expecting register, got {}. Valid register prefixes are r and $.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            elif checkout[0] == 2:
                msg("RegisterNotFoundError: Register {} does not exist.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            elif checkout[0] == 3:
                msg("Warning: Register {} on line {} was negative. It has been converted to a valid register ({})".format(broken[i].split("\n")[0], linenum, checkout[1]), 2)
            elif checkout[0] == 4:
                msg("Warning: Register {} on line {} was above 15. The value has been truncated to the bottom 4 bits. ({})".format(broken[i].split("\n")[0], linenum, checkout[1]), 2)
            else:
                msg("Operand register value good", 4)
            values.append(checkout[1])
        elif operands[i-1] == "l":
            checkout = checklabel(broken[i])
            if checkout[0] == 1:
                msg("ValueError: Expecting label, got {}. Valid label prefix is '.'.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            elif checkout[0] == 2:
                msg("LabelNotFoundError: Label {} has not been created yet.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            else:
                msg("Operand label value good", 4)
            values.append(checkout[1])
        elif operands[i-1] == "a":
            checkout = checkaddr(broken[i])
            if checkout[0] == 1:
                msg("ValueError: Expecting instruction address, got {}. Valid addr prefix is #.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            elif checkout[0] == 2:
                msg("AddressError: Given address {} is not a valid address. Please retry with an integer.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
            elif checkout[0] == 3:
                msg("Warning: Given instruction address {} on line {} was negative, it was switched to address {}.".format(broken[i].split("\n")[0], linenum, checkout[1]), 2)
            elif checkout[0] == 4:
                msg("Warning: Given instruction address on line {} was 0. Instruction line 0 is always a NOP.".format(linenum), 2)
            elif checkout[0] == 5:
                msg("Warning: Given instruction address {} on line {} was above 1023. It has been truncated to the bottom 10 bits. ({})".format(broken[i].split("\n")[0], linenum, checkout[1]))
            else:
                msg("Operand address value good", 4)
            values.append(checkout[1])
        elif operands[i-1] == "c":
            checkout = checkcond(broken[i])
            if checkout[0] == 1:
                msg("Warning: Given condition {} on line {} assures the condition will never be met. This line is redundant.".format(broken[i].split("\n")[0], linenum), 1)
            elif checkout[0] == 2:
                msg("InvalidConditionError: {} is not a valid condition. Please check documentation.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            values.append(checkout[1])
    if error == 0:
        msg("Succesful compile, line {}".format(linenum), 3)
    msg("Values from checkline: {}".format(values), 4)
    return values

if source.split(".")[-1] == "rwpumc":
    msg("Warning: Source filename specified ends in .rwpumc, which is the machine code file extension, not the assembly file extension.", 2)
elif source.split(".")[-1] != "rwpu" or len(source.split(".")) == 1:
    msg("Warning: Source filename specified doesn't end in .rwpu, which is the proper file extension", 2)

if output.split(".")[-1] == "rwpu":
    msg("Warning: Output filename ends in .rwpu, which is the assembly file extension, not the machine code file extension.", 2)
elif output.split(".")[1] != "rwpumc" or len(output.split(".")) == 1:
    msg("Warning: Output filename specified doesn't end in .rwpumc, which is the proper file extension", 2)

if list(lines[len(lines)-1])[-1] != "\n":
    lines[-1] += "\n"

labelindex = 1
for i in lines: # Label detection
    if list(i)[0] == ".": # if the line is a label
        brokeninst = i.split(" ")
        msg("Label found on line", 4)
        validlabel = True
        for j in labelnames:
            if brokeninst[0] == j:
                validlabel = False
                msg("LabelError: Label {} has already been created.\n{}Line {} in input file".format(brokeninst[0], i, line))
        if validlabel:
            labelnames.append(i.split(" ")[0].split("\n")[0])
            labelpos.append(labelindex)
            msg("Label added to instruction address {}".format(labelindex), 4)
        if len(brokeninst) == 1: # if the label is alone on it's line, continue to the next line
            msg("Label was the only thing found on that line", 4)
        else:
            labelindex += 1
    elif list(i)[0] != "/" and len(i) > 1:
        msg("Line had no label.", 4)
        labelindex += 1


for i in lines:
    compilesuccess = True
    line += 1
    msg("Starting new line ({})".format(line), 4)
    instructionbinary = ""
    islabel = 0
    if list(i)[0] == "/": # line comment, (line starts with /)
        msg("Comment on line {}".format(line), 4)
        continue
    brokeninst = i.split(" ")
    if brokeninst[0] == "\n":
        msg("Line is empty. Continuing to next line", 4)
        continue

    msg("Broken instruction: {}".format(brokeninst), 4)
    if list(i)[0] == ".": # if the line is a label
        if len(brokeninst) == 1: # if the label is alone on it's line, continue to the next line
            msg("Label was the only thing found on that line", 4)
            continue
        islabel = 1
    op = brokeninst[islabel].lower().split("\n")[0]
    msg("Compiling line with operation {}".format(op), 3)
    intofunc = []
    for j in range(islabel, len(brokeninst)):
        intofunc.append(brokeninst[j])
    msg("Sending {} into checkline".format(intofunc), 4)

    if op == "nop": # Do nothing
        if error == 0:
            instructionbinary = "000000000000000000"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "add": # reg1 + reg2 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "addc" or op == "adc": # reg1 + reg2 + 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "01"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "addr" or op == "adr": # (reg1 + reg2) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "10"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "addrc" or op == "addcr": # (reg1 + reg2 + 1) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "11"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "cpy": # reg1 -> reg2
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + "0000" + d2b(vals[1], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "inc": # reg1 + 1 -> reg2
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + "0000" + d2b(vals[1], 4) + "01"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "incr": # reg1 + 1 -> reg1
        vals = checkline(intofunc, "r", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + "0000" + d2b(vals[0], 4) + "01"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "lsh": # reg1 << 1 -> reg2
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + d2b(vals[0], 4) + d2b(vals[1], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "rsh": # reg >> 1 -> reg2
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + "0000" + d2b(vals[1], 4) + "10"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "sub": # reg1 - reg2 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "subc" or op == "sbb" or op == "subb": # reg1 - reg2 - 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "subr": # (reg1 - reg2) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "10"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "subrc" or op == "subcr" or op == "sbbr" or op == "sbr" or op == "sbrb": # (reg1 - reg2 - 1) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "11"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "cmp": # sreg1 - reg2 -> void
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + d2b(vals[1], 4) + "000000"
            instruction += 1

    elif op == "neg": # (- reg1) -> reg2
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "00100000" + d2b(vals[0], 4) + d2b(vals[1], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "dec": # reg1 - 1 -> reg2
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + "0000" + d2b(vals[1], 4) + "01"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "decr": # reg1 - 1 -> reg1
        vals = checkline(intofunc, "r", line)
        if error == 0:
            instructionbinary = "0010" + d2b(vals[0], 4) + "0000" + d2b(vals[0], 4) + "01"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "xor": # reg1 ^ reg2 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0011" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "xorr": # (reg1 ^ reg2) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0011" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "10"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "and": # reg1 & reg2 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0100" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "andr": # (reg1 & reg2) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0100" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "10"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "nor": # ~ (reg1 | reg2) -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0101" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "norr" or op == "nrr": # (~ (reg1 ^ reg2)) >> 1 -> reg3
        vals = checkline(intofunc, "rrr", line)
        if error == 0:
            instructionbinary = "0101" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "10"
            msg("Instruction address {} added".format(instruction), 4)
            instruction += 1
    
    elif op == "ldi": # int1 -> reg2
        vals = checkline(intofunc, "ir", line)
        if error == 0:
            instructionbinary = "0110" + d2b(vals[0], 8) + d2b(vals[1], 4) + "00"
            instruction += 1
    
    elif op == "jmp": # addr -> PC if condition
        vals = checkline(intofunc, "lc", line)
        if error == 0:
            instructionbinary = "0111" + d2b(vals[0], 10) + d2b(vals[1], 3) + "0"
            instruction += 1
    
    elif op == "cal" or op == "call": # PC + 1 -> stack; addr -> PC
        vals = checkline(intofunc, "l", line)
        if error == 0:
            instructionbinary = "1000" + d2b(vals[0], 10) + "0000"
            instruction += 1
    
    elif op == "ret" or op == "return": # stack -> PC
        if error == 0:
            instructionbinary = "100100000000000000"
            instruction += 1
    
    elif op == "str": # reg -> RAM @ ptr
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "1010" + d2b(vals[0], 4) + d2b(vals[1], 4) + "000000"
            instruction += 1
    
    elif op == "lod" or op == "load": # RAM @ ptr -> reg
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "1011" + d2b(vals[0], 4) + "0000" + d2b(vals[1], 4) + "00"
            instruction += 1
    
    elif op == "pou" or op == "pout": # reg -> PORT @ ptr
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "1100" + d2b(vals[0], 4) + d2b(vals[1], 4) + "000000"
            instruction += 1
    
    elif op == "pin": # PORT @ ptr -> reg
        vals = checkline(intofunc, "rr", line)
        if error == 0:
            instructionbinary = "1101" + d2b(vals[0], 4) + "0000" + d2b(vals[1], 4) + "00"
            instruction += 1
    
    elif op == "prq" or op == "req": # Wait until port @ ptr acknowledges request
        vals = checkline(intofunc, "r", line)
        if error == 0:
            instructionbinary = "1110" + d2b(vals[0], 4) + "0000000000"
            instruction += 1
    
    elif op == "hlt" or op == "halt" or op == "stp" or op == "stop": # STOP the clock!11!!!11!!1! (help im going insane)
        if error == 0:
            instructionbinary = "111100000000000000"
            instruction += 1
    
    else:
        error += 1
        msg("\033[031mInvalidOperationError: Operation {} was not recognized.\n{}Line {} in input file.\n\033[01m".format(op.upper(), i, line), 1)
        continue
    
    if error == 0:
        msg("Instruction binary: {}".format(instructionbinary), 4)
    binaryinstlist.append(instructionbinary) # Add the instruction to the list of instructions
    
if error != 0:
    msg("The compiler returned {} error(s). The code has not been compiled to machine code.".format(error), 0)
    exit(1)

msg("Assembly reading and translation took %.6f seconds."%(time()-start), 3)

start = time()

for i in binaryinstlist:
    msg("Writing code {} to output".format(i), 4)
    f.write(i + "\n")
f.close()
msg("Machine code writing took %.6f seconds"%(time()-start), 3)

consolebase = min(5, max(0, consolebase))

if consolebase != 0:
    bases = ["","binary (base 2)","quatric (base 4)","octal (base 8)","hexadecimal (base 16)","base 32"]
    print("Here is the machine code in console in {}:\n------------".format(bases[consolebase]))
    del bases
    for i in binaryinstlist:
        print(frombinary(i, consolebase))
    print("------------")
    print("\033[032mDone!\033[0m")
# If you've made it to the end of the code, make sure you like and subscribe and comment! (Yep, I'm definetly going insane)

