import machine
import ssd1306
import time
from machine import I2C, Pin, RTC, ADC

# RTC and initial time
rtc = RTC()
rtc.datetime((2025, 9, 26, 4, 11, 30, 0, 0))

# I2C and OLED setup
i2c = I2C(scl=Pin(20), sda=Pin(22))
oled = ssd1306.SSD1306_I2C(128, 32, i2c)

# Light sensor (ADC)
light_sensor = ADC(Pin(26))

# Button setup
buttonA = Pin(32, Pin.IN, Pin.PULL_UP)
buttonB = Pin(27, Pin.IN, Pin.PULL_UP)
buttonC = Pin(4, Pin.IN, Pin.PULL_UP)

# Debounce setup
DEBOUNCE_MS = 200
_a_last_ms = 0
_b_last_ms = 0
_c_last_ms = 0

# Modes
MODE_NORMAL = 0      # show time
MODE_SET = 1         # set time (hours/minutes)
current_mode = MODE_NORMAL

STATE_HOUR = 0
STATE_MINUTE = 1
current_state = STATE_HOUR

def empty_interrupt(pin):
    pass

def btn_a_irq(pin):

    global buttonB
    global buttonC
    global buttonA
    buttonB.irq(handler=None)
    buttonC.irq(handler=None)
    buttonA.irq(handler=None)

    print("button a handler")



    global current_mode, _a_last_ms
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, _a_last_ms) > DEBOUNCE_MS:
        print("Button A pressed")
        _a_last_ms = current_time
        current_mode = (current_mode + 1) % 2  # Cycle through modes

    buttonB.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_b_irq)
    buttonC.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_c_irq)
    buttonA.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_a_irq)

def btn_b_irq(pin):
    """B: when in set mode toggle between hour and minute. If in alarm mode toggle alarm field."""
    global buttonB
    global buttonC
    global buttonA
    buttonB.irq(handler=None)
    buttonC.irq(handler=None)
    buttonA.irq(handler=None)
    print("button b handler")

    global current_state, current_mode, _b_last_ms
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, _b_last_ms) > DEBOUNCE_MS:
        print("Button B pressed")
        _b_last_ms = current_time
        if current_mode in (MODE_SET):
            current_state = (current_state + 1) % 2  # Toggle between hour/minute

    buttonB.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_b_irq)
    buttonC.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_c_irq)
    buttonA.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_a_irq)

def btn_c_irq(pin):
    """C: increment currently selected field (hour/minute) depending on mode."""
    
    print("Button C handler")
    global buttonB
    global buttonC
    global buttonA
    buttonB.irq(handler=None)
    buttonC.irq(handler=None)
    buttonA.irq(handler=None)
    global _c_last_ms, alarm_hour, alarm_minute
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, _c_last_ms) > DEBOUNCE_MS:
        print("Button C pressed")
        _c_last_ms = current_time
        # In time set mode, increment RTC hour/minute
        if current_mode == MODE_SET:
            if current_state == STATE_MINUTE:
                increment_time("minute")
            else:
                increment_time("hour")

    buttonB.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_b_irq)
    buttonC.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_c_irq)
    buttonA.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_a_irq)

def clear_display():
    oled.fill(0)
    oled.show()

def update_display(time_tuple, light_level=None, highlight=None, show_alarm=False):
    oled.fill(0)
    oled.text("Current Time:", 0, 0)
    h, m, s = time_tuple[4], time_tuple[5], time_tuple[6]
    if highlight == "hour":
        oled.text("[{:02d}]:{:02d}:{:02d}".format(h, m, s), 0, 10)
    elif highlight == "minute":
        oled.text("{:02d}:[{:02d}]:{:02d}".format(h, m, s), 0, 10)
    else:
        oled.text("{:02d}:{:02d}:{:02d}".format(h, m, s), 0, 10)
    oled.text("Brightness: {}".format(light_level), 0, 20)
    oled.show()

def adjust_brightness(light_value):
    brightness = int((light_value))
    brightness = max(0, min(brightness, 255))
    oled.contrast(brightness)

def increment_time(unit):
    dt = list(rtc.datetime())
    if unit == "minute":
        dt[5] = (dt[5] + 1) % 60
    elif unit == "hour":
        dt[4] = (dt[4] + 1) % 24
    rtc.datetime(tuple(dt))

def main_loop():
    clear_display()
    print("Starting clock...")

    while True:
        now = rtc.datetime()
        light_value = light_sensor.read()
        adjust_brightness(light_value)

        # Update display
        if current_mode == MODE_SET and current_state == STATE_MINUTE:
            update_display(now, light_level=light_value, highlight="minute")
        elif current_mode == MODE_SET and current_state == STATE_HOUR:
            update_display(now, light_level=light_value, highlight="hour")
        else:
            update_display(now, light_level=light_value)

        time.sleep(0.1)

# Attach IRQs
buttonA.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_a_irq)
buttonB.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_b_irq)
buttonC.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_c_irq)


main_loop()