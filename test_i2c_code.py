# I2C test script -- copy to the CIRCUITPY drive root and rename to code.py
# Result is reported via onboard RGB LED and serial output:
#   GREEN blink = found both 0x20 and 0x21 (both MCP23017 OK)
#   BLUE blink  = only one chip found (check serial to see which one)
#   RED blink   = no chip found (check pull-ups / SDA / SCK joints)
import board
import busio
import digitalio
import time

# XIAO nRF52840 onboard RGB LED (active low)
leds = {}
for name in ("LED_RED", "LED_GREEN", "LED_BLUE"):
    pin = getattr(board, name, None)
    if pin:
        led = digitalio.DigitalInOut(pin)
        led.direction = digitalio.Direction.OUTPUT
        led.value = True  # off
        leds[name] = led

def show(color, times=1):
    led = leds.get(color)
    if not led:
        return
    for _ in range(times):
        led.value = False
        time.sleep(0.15)
        led.value = True
        time.sleep(0.15)

i2c = busio.I2C(board.SCL, board.SDA)

while True:
    while not i2c.try_lock():
        pass
    found = i2c.scan()
    i2c.unlock()

    names = [hex(a) for a in found]
    has_c = 0x20 in found   # MCP23017C (columns 8-17)
    has_r = 0x21 in found   # MCP23017R (columns 0-7 + rows 0-4)
    print("I2C devices:", names,
          "| C(0x20):", "OK" if has_c else "missing",
          "| R(0x21):", "OK" if has_r else "missing")

    if has_c and has_r:
        show("LED_GREEN", 2)
    elif has_c or has_r:
        show("LED_BLUE", 2)
    else:
        show("LED_RED", 2)

    time.sleep(1)
