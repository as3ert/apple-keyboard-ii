# Matrix scan test -- copy to CIRCUITPY and rename to code.py
# No external libraries needed (raw MCP23017 register access).
#
# What it does:
#   Scans the 5x18 key matrix through the two MCP23017 expanders.
#   Any pressed key is printed to serial as (row, col) and the BLUE LED
#   lights while at least one key is held.
#
# Quick test without the keyboard PCB attached:
#   Short FPC pad 28 (ROW0) to pad 23 (COL0) with tweezers -> should
#   print "pressed: [(0, 0)]" and the blue LED lights up.
#
# Wiring (from board netlist):
#   chip C = 0x20: GPA0-7 = COL8-15, GPB7 = COL16, GPB6 = COL17
#   chip R = 0x21: GPB7..GPB0 = COL0..COL7, GPA0-4 = ROW0-4
import board
import busio
import digitalio
import time

# MCP23017 registers (IOCON.BANK = 0, power-on default)
IODIRA = 0x00
IODIRB = 0x01
GPPUA = 0x0C
GPPUB = 0x0D
GPIOA = 0x12
GPIOB = 0x13
OLATA = 0x14

ADDR_C = 0x20
ADDR_R = 0x21

led_blue = digitalio.DigitalInOut(board.LED_BLUE)
led_blue.direction = digitalio.Direction.OUTPUT
led_blue.value = True  # off (active low)

i2c = busio.I2C(board.SCL, board.SDA)
while not i2c.try_lock():
    pass

buf1 = bytearray(1)

def write_reg(addr, reg, val):
    i2c.writeto(addr, bytes((reg, val)))

def read_reg(addr, reg):
    i2c.writeto_then_readfrom(addr, bytes((reg,)), buf1)
    return buf1[0]

# --- setup ---
# Chip C: everything input with pull-ups (columns 8-17)
write_reg(ADDR_C, IODIRA, 0xFF)
write_reg(ADDR_C, IODIRB, 0xFF)
write_reg(ADDR_C, GPPUA, 0xFF)
write_reg(ADDR_C, GPPUB, 0xFF)
# Chip R: GPB input with pull-ups (columns 0-7),
# GPA rows idle as inputs (hi-Z), latch preloaded low
write_reg(ADDR_R, IODIRA, 0xFF)
write_reg(ADDR_R, IODIRB, 0xFF)
write_reg(ADDR_R, GPPUB, 0xFF)
write_reg(ADDR_R, GPPUA, 0x1F)  # weak pull-ups on row pins while idle
write_reg(ADDR_R, OLATA, 0x00)  # rows output 0 when switched to output

def read_cols():
    """Return list of column indexes currently reading LOW (pressed)."""
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

print("matrix scan running -- press keys (or short FPC pads) ...")
last = []
while True:
    keys = []
    for row in range(5):
        # drive only the active row as output-low, others stay hi-Z
        write_reg(ADDR_R, IODIRA, 0xFF & ~(1 << row))
        time.sleep(0.001)
        for col in read_cols():
            keys.append((row, col))
    write_reg(ADDR_R, IODIRA, 0xFF)  # all rows back to hi-Z

    led_blue.value = not keys  # LED on (low) while any key held
    if keys != last:
        if keys:
            print("pressed:", keys)
        else:
            print("released")
        last = keys
    time.sleep(0.02)
