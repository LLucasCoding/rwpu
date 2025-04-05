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
mcfile = "out.rwpumc"
folder = "schems"
schemname = "rwpucode"

log("Init completed.")

try:
    import mcschematic
except ModuleNotFoundError:
    log("MC schematic module not found. Please install it through pip with the command: pip3 install mcschematic")
    exit(1)

log("Schematic module loaded.")
schem = mcschematic.MCSchematic()
log("Schematic object initialized.")

f = open(mcfile, "r") # The file from which it reads will be configurable.
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
log("Machine code file done ({} lines). Now populating the rest of the P-ROM with 0s".format(linenum-1))
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
schem.save(folder, schemname, mcschematic.Version.JE_1_20_1)
log("Schematic {}.schem saved!".format(schemname))
log("After you load the schematic with WorldEdit, stand on the glass block above the P-ROM (purple) and type //paste -a. The -a is VERY important")
