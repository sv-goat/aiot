from machine import ADC, Pin, PWM
from time import sleep
import utime


button_port = 27

last_button_state = 0 
last_button_timestamp = 0
debounce_delay = 50 

def handler(pin):
    global last_button_state, last_button_timestamp
    current_time = utime.ticks_ms()

    # Only process an interrupt if it's outside the debounce window
    if utime.ticks_diff(current_time, last_button_timestamp) > debounce_delay:
        # Read the current state of the button
        button_state = pin.value()

        # Check if the button's state has actually changed from what we last recorded
        if button_state != last_button_state:
            if button_state == 1:  # A press is a FALLING edge (1 -> 0)
                print("Button pressed!")
            else:  # A release is a RISING edge (0 -> 1)
                print("Button released!")
            
            # Update the last known state
            last_button_state = button_state
        
        # ALWAYS update the timestamp after an interrupt that passes the time check.
        # This is the key fix. It prevents subsequent bounces from being processed.
        last_button_timestamp = current_time

button = Pin(button_port, Pin.IN)

button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=handler)