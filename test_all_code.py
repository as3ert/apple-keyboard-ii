# All-in-one hardware test -- copy to CIRCUITPY and rename to code.py
# This script NEVER crashes, so the LED is always under script control
# (no more confusion with the CircuitPython status LED).
#
# LED meaning (repeats forever):
#   FAST RED non-stop          = I2C init failed: no pull-up on SDA/SCL
#   RED + BLUE alternating     = bus OK but a MCP23017 chip is missing
#   GREEN heartbeat (1 blink/s)= both chips OK, matrix scanner running
#   SOLID WHITE (all 3 on)     = a key/short is detected right now
import board
import busio
import digitalio
import time

LED_NAMES = ("LED_RED", "LED_GREEN", "LED_BLUE")
leds = {}
for name in LED_NAMES:
    pin = getattr(board, name, None)
    if pin:
        d = digitalio.DigitalInOut(pin)
        d.direction = digitalio.Direction.OUTPUT
        d.value = True  # off (active low)
        leds[name] = d

def set_leds(r=False, g=False, b=False):
    if "LED_RED" in leds:
        leds["LED_RED"].value = not r
    if "LED_GREEN" in leds:
        leds["LED_GREEN"].value = not g
    if "LED_BLUE" in leds:
        leds["LED_BLUE"].value = not b

def fast_red_forever(msg):
    print("FATAL:", msg)
    while True:
        set_leds(r=True)
        time.sleep(0.1)
        set_leds()
        time.sleep(0.1)

# ---- I2C init (catch the no-pull-up error) ----
try:
    i2c = busio.I2C(board.SCL, board.SDA)
except RuntimeError as e:
    fast_red_forever("I2C init failed -> " + str(e))

while not i2c.try_lock():
    pass

# ---- chip presence ----
ADDR_C = 0x20
ADDR_R = 0x24  # A2=3V3, A1=A0=GND -> 0x20 + 4 (was wrongly 0x21 before)
found = i2c.scan()
print("I2C scan:", [hex(a) for a in found])
while not (ADDR_C in found and ADDR_R in found):
    missing = [hex(a) for a in (ADDR_C, ADDR_R) if a not in found]
    print("missing chip(s):", missing, "- rescanning ...")
    set_leds(r=True)
    time.sleep(0.3)
    set_leds(b=True)
    time.sleep(0.3)
    set_leds()
    found = i2c.scan()

print("both MCP23017 found - starting matrix scan")

# ---- MCP23017 registers (IOCON.BANK = 0 default) ----
IODIRA = 0x00
IODIRB = 0x01
GPPUA = 0x0C
GPPUB = 0x0D
GPIOA = 0x12
GPIOB = 0x13
OLATA = 0x14

buf1 = bytearray(1)

def write_reg(addr, reg, val):
    i2c.writeto(addr, bytes((reg, val)))

def read_reg(addr, reg):
    i2c.writeto_then_readfrom(addr, bytes((reg,)), buf1)
    return buf1[0]

# Chip C: all inputs with pull-ups (columns 8-17)
write_reg(ADDR_C, IODIRA, 0xFF)
write_reg(ADDR_C, IODIRB, 0xFF)
write_reg(ADDR_C, GPPUA, 0xFF)
write_reg(ADDR_C, GPPUB, 0xFF)
# Chip R: GPB inputs with pull-ups (columns 0-7), GPA rows hi-Z, latch low
write_reg(ADDR_R, IODIRA, 0xFF)
write_reg(ADDR_R, IODIRB, 0xFF)
write_reg(ADDR_R, GPPUB, 0xFF)
write_reg(ADDR_R, GPPUA, 0x1F)
write_reg(ADDR_R, OLATA, 0x00)

def read_cols():
    pressed = []
    gb_r = read_reg(ADDR_R, GPIOB)   # COL0..7  on bits 7..0
    ga_c = read_reg(ADDR_C, GPIOA)   # COL8..15 on bits 0..7
    gb_c = read_reg(ADDR_C, GPIOB)   # COL16 = bit7, COL17 = bit6
    for col in range(8):
        if not (gb_r >> (7 - col)) & 1:
            pressed.append(col)
    for col in range(8):
        if not (ga_c >> col) & 1:
            pressed.append(8 + col)
    if not (gb_c >> 7) & 1:
        pressed.append(16)
    if not (gb_c >> 6) & 1:
        pressed.append(17)
    return pressed

last = []
beat = time.monotonic()
beat_on = False
while True:
    keys = []
    for row in range(5):
        write_reg(ADDR_R, IODIRA, 0xFF & ~(1 << row))
        time.sleep(0.001)
        for col in read_cols():
            keys.append((row, col))
    write_reg(ADDR_R, IODIRA, 0xFF)

    if keys:
        set_leds(r=True, g=True, b=True)  # white = key detected
    else:
        # green heartbeat: short blink once per second
        now = time.monotonic()
        if beat_on and now - beat > 0.1:
            set_leds()
            beat_on = False
            beat = now
        elif not beat_on and now - beat > 0.9:
            set_leds(g=True)
            beat_on = True
            beat = now

    if keys != last:
        print("pressed:" if keys else "released", keys if keys else "")
        last = keys
    time.sleep(0.02)
