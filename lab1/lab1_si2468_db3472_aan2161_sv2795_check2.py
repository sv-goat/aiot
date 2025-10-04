from machine import Pin
import utime
import neopixel
# Power-enable for NeoPixel
pwr = Pin(2, Pin.OUT)
pwr.value(1) # turn on power
builtin_led = Pin(13, Pin.OUT)
np_led = neopixel.NeoPixel(Pin(0, Pin.OUT), 1)
builtin_led.value(1) # Built in LED - 1 is on
np_led[0] = (0, 0, 0) # NeoPixel LED - (0,0,0) is off
np_led.write()

fast_time = 400
slow_time = 2000

last_fast = utime.ticks_ms()
last_slow = utime.ticks_ms()

led_values = (255, 255, 255)

while True:

	cur_time = utime.ticks_ms()

	if utime.ticks_diff(cur_time, last_fast) >= fast_time:
		last_fast = cur_time
		builtin_led.value(not builtin_led.value())

	if utime.ticks_diff(cur_time, last_slow) >= slow_time:
		last_slow = cur_time
		led_values = (255 - led_values[0], 255 - led_values[1], 255 - led_values[2])
		np_led[0] = led_values
		np_led.write()



