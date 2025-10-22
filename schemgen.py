from time import time

start = time()

def log(msg):
    global start
    timestamp = "%.6f"%(time()-start)
    while len(timestamp) < 12:
        timestamp = " " + timestamp
    print("[{}] {}".format(timestamp, msg))

# These will be configurable through .config
maxline = 255
mcfile = "mcode.rwpumc"
folder = "schems"
schemname = "rwpucode"

log("Starting init, opening .config file...")
try:
    f = open(".config", "r")
    configlines = f.readlines()
    f.close()
    log("File closed. Processing settings...")
    for i in configlines:
        if (len(i) > 1):
            i = i.split("\n")[0]    
            setting = i.split(" ")[0]
            val = i.split(" ")[1]
            if setting == "mcode":
                mcfile = val
                if mcfile.split(".")[-1] == "rwpu":
                    log("Note: The machine code file ends in .rwpu, which is the extension for the assembly language.")
                elif mcfile.split(".")[-1] != "rwpumc":
                    log("Note: The input machine code file does not end in rwpumc, which is the correct extension.")
            elif setting == "schemfolder":
                folder = val
            elif setting == "schem" or setting == "schemname":
                schemname = val
            elif setting == "maxline":
                try:
                    val = int(val)
                    if val < 1:
                        log("Config file error! The maximum line setting has to be a positive integer! ({} given)")
                except ValueError:
                    log("Config file error! Setting {} requires an integer ({} given)".format(setting, val))
                    exit(1)
                maxline = val
            elif not (setting == "asm" or setting == "verbosity" or setting == "consolebase"):
                log("Config file error! Setting {} not recognized.".format(setting))
                exit(1)
except FileNotFoundError:
    log("The .config file does not exist. All settings are at their default values.")

log("Init completed. Loading schematic module.")

try:
    import mcschematic
except ModuleNotFoundError:
    log("MC schematic module not found. Please install it through pip with the command: pip3 install mcschematic")
    exit(1)

log("Schematic module loaded.")
schem = mcschematic.MCSchematic()
log("Schematic object initialized.")

try:
    f = open(mcfile, "r") # The file from which it reads will be configurable.
except FileNotFoundError:
    log("Error: The machine code file {} does not exist.".format(mcfile))
    exit(1)
lines = f.readlines()
f.close()
log("Machine code lines read.")

linenum = 1
x = 2
z = -1

for i in lines:
    if len(i) == 19:
        binary = list(i.split("\n")[0])
        y = 0
        for j in binary:
            y -= 2
            if j == "0":
                schem.setBlock((x, y, z), "minecraft:black_concrete")
            elif j == "1":
                if z & 2 == 0:
                    schem.setBlock((x, y, z), "minecraft:repeater[facing=south]")
                else:
                    schem.setBlock((x, y, z), "minecraft:repeater[facing=north]")
            else:
                log("Invalid character in machine code file: {} at line {}".format(j, linenum))
                exit(1)
    else:
        log("Invalid instruction length in machine code file: Length {} at line {}.".format(len(i)-1, linenum))
        exit(1)
    linenum += 1
    x += 2
    if x == 64:
        x = 0
        if z & 2 == 0:
            z += 10
        else:
            z += 2
if linenum-1 > maxline:
    log("Warning: Your code exceeds {} instructions ({} instructions.) If you have an upgraded P-ROM, set the maxline value in .config.".format(maxline, linenum-1))
log("Machine code file done ({} instructions). Populating the rest of the P-ROM with NOPs...".format(linenum-1))
usage = linenum-1
l = linenum
for linenum in range(l, maxline+1):
    for y in range(-2, -37, -2):
        schem.setBlock((x, y, z), "minecraft:black_concrete")
    x += 2
    if x == 64:
        x = 0
        if z & 2 == 0:
            z += 10
        else:
            z += 2

log("Population complete.")

log("Starting schematic saving...")

try:
    schem.save(folder, schemname, mcschematic.Version.JE_1_20_1)
except FileNotFoundError:
    log("Error: The folder '{}' (where the schematic was supposed to be saved) does not exist. Please create the folder and try again.".format(folder))
    exit(1)

log("Schematic {}.schem saved!".format(schemname))
log("After you load the schematic with WorldEdit, stand on the glass block above the P-ROM (purple) and type //paste -a. The -a is VERY important")

if maxline > 1023:
    log("Warning: The maximum line setting exceeds 1023, which is higher than the Program Counter or ISA can support. (Pasting the schematic can cause unintended consequences.)")

log("Success!")

log("P-ROM usage: {}/{} Kib | {}%".format(round(usage*18/1024, 2), round(maxline*18/1024, 2), round((usage)/maxline*100, 1)))
usage = min(usage, maxline)
hashtags = round((usage)/maxline*40)
log("P-ROM usage: [" + "#"*hashtags + "_"*(40-hashtags) + "]")

# pluh
