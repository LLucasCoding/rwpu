f = open(input("Enter file name: "), "r") # will be replaced by command line argument
lines = f.readlines()

instruction = 1 # Position of current instruction
instructionbinary = "" # Binary value for that instruction, which gets pushed to instruction list when it is done.
binaryinstlist = [] # Final binary instruction list
labelnames = [] # List of all labels
labelpos = [] # List of label positions
stackdepth = 0 # To track stack overflow
baseref = list("0123456789ABCDEFGHIJKLMNOPQRSTUV") # All characters for bases up to 32
line = 0 # Line, to tell the user what line to look at when an error occurs
error = False # Error variable, doesn't write to file or display final code result if there is a fatal error.

def format(n, l): # format integer n to have l places minimum
    n = str(n)
    while len(n) < l:
        n = "0" + n
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

for i in lines:
    line += 1
    instructionbinary = ""
    islabel = 0
    if list(i)[0] == "/": # line comment, (line starts with /)
        continue
    brokeninst = i.split(" ")
    if list(i)[0] == ".": # if the line is a label
        labelnames.append(lines.split(" ")[0])
        labelpos.append(instruction)
        if len(brokeninst) == 1: # if the label is alone on it's line, continue to the next line
            continue
        islabel = 1
    op = brokeninst[islabel].lower()
    if op == "add":
        # addition code
        pass
    else:
        error = True
        print("Compiler Error: Operation {} on line {} was not recognized. Please refer to ISA for list of instructions and pseudoinstructions.".format(op, line))
        exit(0)
    

