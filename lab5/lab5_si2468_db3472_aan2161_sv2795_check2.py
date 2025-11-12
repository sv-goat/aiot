import ssd1306
import time
from machine import I2C, Pin, RTC, ADC, SPI
import gc
import urequests as requests
import ujson as json
import network
import time
import socket

# wifi connection
wifi = network.WLAN(network.STA_IF)  
wifi.active(True)
print("📡 Pulling up to WiFi… hold up")
wifi.connect('Columbia University', '')

# wait until it's actually locked in
while not wifi.isconnected():
    print("still cooking…")
    time.sleep(1)

print("Connected! IP:", wifi.ifconfig()[0])
gc.collect()

# ---- Simple HTTP Server ----
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
created_socket = socket.socket()
created_socket.bind(addr)
created_socket.listen(1)

print("Listening on", addr)

print("Hit me at: ", wifi.ifconfig()[0])

def handle_request(conn):
    global state_display_time
    state_display_time = False
    try:
        req = b""
        # Keep reading until headers are done
        while b"\r\n\r\n" not in req:
            chunk = conn.recv(512)
            if not chunk:
                break
            req += chunk

        header, _, rest = req.partition(b"\r\n\r\n")
        header_str = header.decode()
        content_length = 0

        for line in header_str.split("\r\n"):
            if "Content-Length:" in line:
                content_length = int(line.split(":")[1].strip())

        # Read remaining body bytes
        body = rest
        while len(body) < content_length:
            chunk = conn.recv(512)
            if not chunk:
                break
            body += chunk

        body_str = body.decode()

        # --- Parse JSON and execute ---
        if "POST /run" not in header_str:
            conn.send(b"HTTP/1.1 404 Not Found\r\n\r\n")
            return

        data = json.loads(body_str)
        func_name = data.get("name")
        func = COMMANDS.get(func_name)[0] if func_name in COMMANDS else None
        num_args = COMMANDS.get(func_name)[1] if func_name in COMMANDS else 0

        if func:
            args = data.get("args", [])
            if len(args) != num_args:
                response = json.dumps({"ok": False, "error": "invalid number of arguments"})
                conn.send(b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n\r\n" + response.encode())
                return
            result = func(*args) if num_args > 0 else func()
            response = json.dumps({"ok": True, "result": result})
        else:
            response = json.dumps({"ok": False, "error": "unknown function"})

        conn.send(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n")
        conn.send(response.encode())

    except Exception as e:
        err = json.dumps({"ok": False, "error": str(e)})
        conn.send(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + err.encode())
    finally:
        conn.close()

# Wrap up the code in a while loop to enable retry
while True:
    # Step 1: Get your location using ip-api.com
    loc_resp = requests.get("http://ip-api.com/json/")
    loc_data = loc_resp.json()
    if loc_data.get("status") != "success":
        content = loc_resp.content
        print("Failed. Reason: ", content)
        del content
        del loc_data
        del loc_resp
        gc.collect()
        time.sleep(5)
    else:
        loc_resp.close()
        print("We in bois")
        break

city = loc_data.get("city")
# If space, add a plus sign
city = city.replace(" ", "+")
lat = loc_data.get("lat")
lon = loc_data.get("lon")
location_coords = f"(lat: {lat}, lon: {lon})"

del loc_data
del loc_resp
gc.collect()

# %t = temperature, %C = condition. You can tweak the format as needed.
weather_url = f"http://wttr.in/{city}?format=%t,%C"
del city
gc.collect()

while True:
    gc.collect()
    r = requests.get(weather_url, timeout=15)
    try:
        s = r.text.strip()   # very small response (e.g., "+22°C,Partly cloudy")
    finally:
        try:
            r.close()
        except:
            pass

    if not s or "Unknown location" in s:
        gc.collect()
        time.sleep(5)
        continue

    # Parse the short string safely
    if "," in s:
        temp, cond = s.split(",", 1)
        weather_data_val = f"{temp.replace('°', '*')}, {cond}"
        break
    else:
        gc.collect()
        time.sleep(5)
        
# RTC and initial time
rtc = RTC()
rtc.datetime((2025, 9, 26, 4, 11, 30, 0, 0))

local_time = time.localtime()
timestamp = f"{local_time[3]:02}:{local_time[4]:02}"
del local_time

weather_with_timestamp = f"{weather_data_val} at {timestamp}"

net_sh_url = 'http://ntfy.sh/skibidi_rizz'
requests.post(net_sh_url, data=location_coords + "\n" + weather_with_timestamp)

# I2C and OLED setup
i2c = I2C(scl=Pin(20), sda=Pin(22))
OLED_X_PIXELS = 128
OLED_Y_PIXELS = 32
oled = ssd1306.SSD1306_I2C(OLED_X_PIXELS, OLED_Y_PIXELS, i2c)

# Light sensor (ADC)
light_sensor = ADC(Pin(34))

# Button setup
buttonA = Pin(32, Pin.IN, Pin.PULL_UP)
buttonB = Pin(27, Pin.IN, Pin.PULL_UP)
buttonC = Pin(4, Pin.IN, Pin.PULL_UP)
#27,32,33
# Output for alarm (buzzer/vibration motor)
alarm_output = Pin(12, Pin.OUT)

# Debounce setup
DEBOUNCE_MS = 200
_a_last_ms = 0
_b_last_ms = 0
_c_last_ms = 0

# Modes
MODE_NORMAL = 0      # show time
MODE_SET = 1         # set time (hours/minutes)
MODE_ALARM = 2       # set alarm
current_mode = MODE_NORMAL

STATE_HOUR = 0
STATE_MINUTE = 1
current_state = STATE_HOUR

# Alarm settings
alarm_hour = 11
alarm_minute = 32
alarm_enabled = True
alarm_triggered = False

# Text positions
previous_text_position = (0, 15)
ACCELERATION_THRESHOLD = 0.2
max_length = 0

# === SPI Setup ===
# Try the common HSPI pins on Feather Huzzah ESP32
spi = SPI(
    1, baudrate=5000000, polarity=1, phase=1,
    sck=Pin(5), mosi=Pin(19), miso=Pin(21)
)
cs = Pin(15, Pin.OUT)
cs.value(1)  # Deselect device by default

# === SPI Commands ===
SPI_READ = 1 << 7
SPI_SINGLE_BYTE = 0 << 6

# some initilization of registers on the accelerometer

def write_register(register, value):
    cs.value(0)
    spi.write(bytearray([register & 0x3F, value]))  # bit7=0 for write, bit6=0 for single byte
    cs.value(1)
    

def initialize_adxl345():
    # Set data format 
    write_register(0x31, 0x00)
    # Set output data rate to 100 Hz
    write_register(0x2C, 0x0A)
    # Disable interrupts
    write_register(0x2E, 0x00)
    # FIFO bypass mode
    write_register(0x38, 0x00)
    # Enable measurement mode
    write_register(0x2D, 0x08)
    print("[INIT] ADXL345 initialized.")

# read the acceleration of the device
def read_acceleration():
    # 6 bytes starting at 0x32 (DATAX0)
    start_reg = 0x32
    read_cmd = start_reg | 0xC0  # 11000000 = multi-byte read
    buf = bytearray(6)

    cs.value(0)
    spi.write(bytearray([read_cmd]))
    spi.readinto(buf)
    cs.value(1)

    x = buf[1] << 8 | buf[0]
    y = buf[3] << 8 | buf[2]
    z = buf[5] << 8 | buf[4]

    if x > 32767:
        x -= 65536

    if y > 32767:
        y -= 65536

    if z > 32767:
        z -= 65536

    # Scale to g-units (assuming ±2g, 4 mg/LSB)
    x_g = x * 0.0039
    y_g = y * 0.0039
    z_g = z * 0.0039

    return (round(x_g, 3), round(y_g, 3), round(z_g, 3))


# === Test Device ID ===
def read_device_id():
    cs.value(0)
    spi.write(bytearray([SPI_READ | SPI_SINGLE_BYTE | 0x00]))  # DEVID register = 0x00
    buf = bytearray(1)
    spi.readinto(buf)
    cs.value(1)
    return buf[0]




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
        current_mode = (current_mode + 1) % 3  # Cycle through modes

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
        if current_mode in (MODE_SET, MODE_ALARM):
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
        # In alarm set mode, increment alarm values
        elif current_mode == MODE_ALARM:
            if current_state == STATE_HOUR:
                alarm_hour = (alarm_hour + 1) % 24
            else:
                alarm_minute = (alarm_minute + 1) % 60

    buttonB.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_b_irq)
    buttonC.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_c_irq)
    buttonA.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_a_irq)

def clear_display():
    oled.fill(0)
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

def check_alarm(now):
    global alarm_triggered
    if alarm_enabled and not alarm_triggered:
        current_hour = now[4]
        current_minute = now[5]
        if current_hour == alarm_hour and current_minute == alarm_minute:
            alarm_triggered = True
            return True
    return False

def trigger_alarm_visual_audio():
    # Flash display and turn on buzzer/vibration
    for i in range(10):
        oled.fill(0)
        oled.text("!!! ALARM !!!", 10, 10)
        oled.show()
        alarm_output.value(1)
        time.sleep(0.2)
        oled.fill(0)
        oled.show()
        alarm_output.value(0)
        time.sleep(0.2)


# STANDARDIZED COMMAND FUNCTIONS
def screen_on():
    global SCREEN_ENABLED
    SCREEN_ENABLED = True
    display_time()
    return "Screen ON"

def screen_off():
    global SCREEN_ENABLED, state_display_time
    state_display_time = False
    SCREEN_ENABLED = False
    oled.fill(0)
    oled.show()
    return "Screen OFF"

'''
def display_time(duration_sec=None):
    if not SCREEN_ENABLED:
        return "Screen is off"

    start_ms = time.ticks_ms()
    while state_display_time:
        # Stop after a duration if provided
        if duration_sec is not None:
            if time.ticks_diff(time.ticks_ms(), start_ms) > duration_sec * 1000:
                break

        # Read RTC: (year, month, day, weekday, hour, min, sec, subsecs)
        y, m, d, wd, hh, mm, ss, sub = rtc.datetime()
        time_str = f"{hh:02d}:{mm:02d}:{ss:02d}"

        # Draw
        oled.fill(0)
        oled.text("Time:", 5, 5)
        oled.text(time_str, 5, 16)
        oled.show()

        # Sleep to roughly align to 1s ticks
        time.sleep(1)
    return "Stopped live clock"
'''

def display_time():
    global state_display_time
    
    if not SCREEN_ENABLED: 
        return "Screen is off" 

    state_display_time = True
    now = rtc.datetime() 
    time_str = f"{now[4]:02d}:{now[5]:02d}:{now[6]:02d}" 
    display_multiline_text("Time:", time_str) 
    return f"Displayed time: {time_str}"

def display_message(message):
    if not SCREEN_ENABLED: return "Screen is off"
    display_multiline_text("Message:", str(message))
    return "Displayed message"

def set_alarm(hour, minute):
    global alarm_hour, alarm_minute, alarm_enabled, alarm_triggered
    try:
        print(f"Setting alarm for {hour}:{minute}")
        alarm_hour = int(hour)
        alarm_minute = int(minute)
        alarm_enabled = True
        alarm_triggered = False  # Reset trigger when a new alarm is set
        time_str = f"{alarm_hour:02d}:{alarm_minute:02d}"
        display_multiline_text("Alarm Set:", time_str)
        return f"Alarm set for {time_str}"
    except (ValueError, TypeError):
        return "Invalid time format for alarm"

def display_location():
    if not SCREEN_ENABLED: return "Screen is off"
    display_multiline_text("Location:", location_coords)
    return f"Displayed location"
    
def display_weather():
    if not SCREEN_ENABLED: return "Screen is off"
    display_multiline_text("Weather:", weather_data_val)
    return f"Displayed weather"

COMMANDS = {
    "screen_on":        (screen_on,        0),
    "screen_off":       (screen_off,       0),
    "display_time":     (display_time,     0),
    "display_text":     (display_message,  1), # payload message
    "set_alarm":        (set_alarm,        2),  # hour, minute
    "display_location": (display_location, 0),
    "display_weather":  (display_weather,  0),
}

# Put this near your globals after you construct `oled`
SCREEN_ENABLED = True
state_display_time = False

# --- Simple OLED display (no wrapping) ---
def display_multiline_text(header, body):
    """
    Show a header and body on 128x32 OLED without wrapping or pagination.
    - header: shown on first line (max 16 chars)
    - body: shown starting second line (max 3 lines)
    """
    if not globals().get("SCREEN_ENABLED", True):
        return "Screen is off"

    oled.fill(0)
    # Cap the length of the line to 16 and then wrap them below
    body_str = str(body)
    indu_lines = body_str.split("\n")
    res = []
    for line in indu_lines:
        if len(line) > 15:
            # Break into chunks of 15
            for i in range(0, len(line), 15):
                res.append(line[i:i+15])
        else:
            res.append(line)
    # Just three lines
    lines = res[:3]
    for i, line in enumerate(lines):
        oled.text(line, 3, 3 + (i + 1) * 8)
    oled.show()
    return "OK"


# LLM SERVER IMPLEMENTATION


# MAIN LOOP 
def main_loop():
    global addr, created_socket, state_display_time
    # initialize the important registers to their default values first
    initialize_adxl345()
    clear_display()
    print("Starting clock with alarm feature...")
    created_socket.settimeout(0.5)   # 0.5s polling interval
    while True:
        if check_alarm(rtc.datetime()):
            trigger_alarm_visual_audio()
        if state_display_time:
            display_time()
        try:
            conn, addr = created_socket.accept()
        except OSError as e:
            # Timeout occurred, just continue the loop
            continue
        handle_request(conn)

# Attach IRQs
buttonA.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_a_irq)
buttonB.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_b_irq)
buttonC.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_c_irq)


main_loop()