from time import time

filename = input("Enter file name: ")
try:
    f = open(filename, "r") # will be replaced by command line argument
except FileNotFoundError:
    print("\033[031m\033[01mThe specified file was not found. Please double check your path and filename\033[0m")
    exit(0)

start = time()

lines = f.readlines()

warnlevel = 4 # 0 = silent except at end if error, 1 = errors only, 2 = errors and warnings, 3 = logs and errors and warnings, 4 = verbose; 2 = default

instruction = 1 # Position of current instruction
instructionbinary = "" # Binary value for that instruction, which gets pushed to instruction list when it is done.
binaryinstlist = [] # Final binary instruction list
labelnames = [] # List of all labels
labelpos = [] # List of label positions
stackdepth = 0 # To track stack overflow
baseref = list("0123456789ABCDEFGHIJKLMNOPQRSTUV") # All characters for bases up to 32
line = 0 # Line, to tell the user what line to look at when an error occurs
error = 0 # Error variable, doesn't write to file or display final code result if there is a fatal error.
compilesuccess = True # If a line was compiled properly

def msg(m, level):
    formatter = ""
    global warnlevel
    if level <= 1:
        formatter = "\033[031m"
    elif level == 2:
        formatter = "\033[033m"
    if level <= warnlevel:
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

def log2int(integer): # log2(n) rounded down
    result = -1
    mask = 1
    while mask <= integer:
        result += 1
        mask <<= 1
    return result

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
    valid = False
    global labelnames
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
                msg("Warning: Register {} on line {} was above 15. The value has been truncated to the bottom 4 bits. ({})".format(broken[i].split("\n")[0], line, linenum, checkout[1]), 2)
            else:
                msg("Operand register value good", 4)
            values.append(checkout[1])
        elif operands[i-1] == "l":
            checkout = checklabel(broken[i])
            if checkout[0] == 1:
                msg("ValueError: Expecting label, got {}. Valid label prefix is '.'.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum), 1)
                error += 1
            elif checkout[0] == 2:
                msg("LabelNotFoundError: Label {} has not been created yet.\n{}Line {} in input file.\n".format(broken[i].split("\n")[0], line, linenum))
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
    if error == 0:
        msg("Succesful compile, line {}".format(linenum), 3)
    return values

if filename.split(".")[-1] == "rwpumc":
    msg("Warning: Filename specified ends in .rwpumc, which is the machine code file extension, not the assembly file extension.", 2)
elif filename.split(".")[-1] != "rwpu" or len(filename.split(".")) == 1:
    msg("Warning: Filename specified doesn't end in .rwpu, which is the proper file extension", 2)

if list(lines[len(lines)-1])[-1] != "\n":
    lines[-1] += "\n"

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
        msg("Label found on line", 4)
        validlabel = True
        for j in labelnames:
            if brokeninst[0] == j:
                validlabel = False
                msg("LabelError: Label {} has already been created.\n{}Line {} in input file".format(brokeninst[0], i, line))
        if validlabel:
            labelnames.append(i.split(" ")[0])
            labelpos.append(instruction)
            msg("Label added to instruction address {}".format(instruction), 4)
        if len(brokeninst) == 1: # if the label is alone on it's line, continue to the next line
            msg("Label was the only thing found on that line", 4)
            continue
        islabel = 1
    op = brokeninst[islabel].lower()
    msg("Compiling line with operation {}".format(op), 3)
    intofunc = []
    for j in range(islabel, len(brokeninst)):
        intofunc.append(brokeninst[j])
    msg("Sending {} into checkline".format(intofunc), 4)
    if op == "add":
        vals = checkline(intofunc, "rrr", line)
        msg("Recived values {}.".format(vals), 4)
        if error == 0:
            instructionbinary = "0001" + d2b(vals[0], 4) + d2b(vals[1], 4) + d2b(vals[2], 4) + "00"
            msg("Instruction address {} added".format(instruction), 4)
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

msg(".rwpu reading and translation took %.6f seconds."%(time()-start), 3)
