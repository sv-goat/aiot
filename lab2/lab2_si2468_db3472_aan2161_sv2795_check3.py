from machine import ADC, Pin, PWM
from time import sleep
import utime

light_sensor_input_port = 36
output_port = 15
button_port = 27

last_button_state = 0 
last_button_timestamp = 0
debounce_delay = 50 
nonsense_on = False

def handler(pin):
    #print("Button state", pin.value())
    global last_button_state, last_button_timestamp, nonsense_on
    current_time = utime.ticks_ms()
    #print("Interrupt detected")
    #print("Current time:", current_time)

    # Only process an interrupt if it's outside the debounce window
    if utime.ticks_diff(current_time, last_button_timestamp) > debounce_delay:
        # Read the current state of the button
        button_state = pin.value()

        # Check if the button's state has actually changed from what we last recorded
        if button_state != last_button_state:
            if button_state == 1:  # A press is a FALLING edge (1 -> 0)
                print("Button pressed!")
                nonsense_on = True
            else:  # A release is a RISING edge (0 -> 1)
                print("Button released!")
                nonsense_on = False
            
            # Update the last known state
            last_button_state = button_state
        
        # ALWAYS update the timestamp after an interrupt that passes the time check.
        # This is the key fix. It prevents subsequent bounces from being processed.
        last_button_timestamp = current_time

light_sensor = ADC(Pin(light_sensor_input_port))

led = PWM(Pin(output_port), freq=1000)

light_sensor.width(ADC.WIDTH_12BIT)  

button = Pin(button_port, Pin.IN)

button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=handler)
#print("Main loop iteration")

while True:
    reading = light_sensor.read()  # Read the analog value (0–4095)
    # clamp reading between 0 and 1023
    reading = max(0, min(768, reading))
    if nonsense_on:
        led.duty(reading)
    else:
        led.duty(0)
    sleep(0.1)  # 10 sample per second ( aka 10 Hz frequence )