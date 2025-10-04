from machine import Pin, I2C, RTC, PWM, ADC
import utime
from utime import ticks_diff
from utime import ticks_ms
import ssd1306

i2c = I2C(sda=Pin(22), scl=Pin(20))
display = ssd1306.SSD1306_I2C(128, 32, i2c)

sensor_pin = ADC(Pin(34))
light_val = sensor_pin.read_u16()

led = PWM(Pin(13), 100)
led.duty_u16(0)

# Look at the pairs of pins labeled A, B, C on the SSD1306
increment_digit_button = Pin(4, Pin.IN, Pin.PULL_UP) 
edit_alarm_time_button = Pin(5, Pin.IN, Pin.PULL_UP)  
switch_menu_button = Pin(27, Pin.IN, Pin.PULL_UP)   

DEBOUNCE_TIME_MS = 50

# REIMPLEMENTING THE BUTTON DEBOUNCER FROM LAB 2, but for each button now. 

# Button state tracking
switch_menu_last_state = switch_menu_button.value()
edit_alarm_time_last_state = edit_alarm_time_button.value()  
increment_digit_last_state = increment_digit_button.value()  

def switch_menu_isr(Pin):
    global switch_menu_last_press_time
    switch_menu_last_press_time = ticks_ms()
    switch_menu_button.irq(trigger=None)

def edit_alarm_time_isr(Pin):  
    global edit_alarm_time_last_press_time
    edit_alarm_time_last_press_time = ticks_ms()
    edit_alarm_time_button.irq(trigger=None)

def increment_digit_isr(Pin):  
    global increment_digit_last_press_time
    increment_digit_last_press_time = ticks_ms()
    increment_digit_button.irq(trigger=None)

# Set up the interrupts for each button. 
switch_menu_button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=switch_menu_isr)
edit_alarm_time_button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=edit_alarm_time_isr)  
increment_digit_button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=increment_digit_isr)  

rtc = RTC()
alarm_set = False
alarm_triggered = False
alarm_time = [0, 0]  # [hour, minute]

switch_menu_last_press_time = 0
edit_alarm_time_last_press_time = 0
increment_digit_last_press_time = 0  

current_screen = "alarm"  # Only alarm screen for now

# Edit mode variables
edit_mode = False
editing_hours = True  # True = editing hours, False = editing minutes
pulse_counter = 0  # For pulsing effect
time_mode = False

while True:
    print("Increment button value:", increment_digit_button.value())
    # Debounce and handle edit alarm time button
    if edit_alarm_time_button.value() != edit_alarm_time_last_state:
        if ticks_diff(ticks_ms(), edit_alarm_time_last_press_time) > DEBOUNCE_TIME_MS:
            edit_alarm_time_last_state = edit_alarm_time_button.value()
            if not edit_alarm_time_button.value():  # Button pressed
                if time_mode:
                    rtc.datetime((year, month, day, weekday, ((hour - 1) % 24), minute, second, subseconds))
                else:
                    if not edit_mode:
                        # Enter edit mode, start with hours
                        edit_mode = True
                        editing_hours = True
                        pulse_counter = 0
                    else:
                        # Switch between hours and minutes
                        editing_hours = not editing_hours
                        pulse_counter = 0
            # re-enable the interrupt
            edit_alarm_time_button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=edit_alarm_time_isr)

    # Debounce and handle increment digit button
    if increment_digit_button.value() != increment_digit_last_state:
        if ticks_diff(ticks_ms(), increment_digit_last_press_time) > DEBOUNCE_TIME_MS:
            increment_digit_last_state = increment_digit_button.value()
            if not increment_digit_button.value():  # Button pressed
                if time_mode:
                    rtc.datetime((year, month, day, weekday, ((hour + 1) % 24), minute, second, subseconds))
                else:
                    if edit_mode:
                        # In edit mode: increment the current digit
                        if editing_hours:
                            alarm_time[0] = (alarm_time[0] + 1) % 24  # Increment hours (0-23)
                        else:
                            alarm_time[1] = (alarm_time[1] + 1) % 60  # Increment minutes (0-59)
                    else:
                        # Activates time mode, where the clock time can be changed. 
                        time_mode = True
                        alarm_set = False
            increment_digit_button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=increment_digit_isr)
    
    if switch_menu_button.value() != switch_menu_last_state:
        if ticks_diff(ticks_ms(), switch_menu_last_press_time) > DEBOUNCE_TIME_MS:
            switch_menu_last_state = switch_menu_button.value()
            if not switch_menu_button.value(): # If button pressed:
                # If time mode is on, this is how you leave it. 
                if time_mode:
                    time_mode = False
                else:
                    if edit_mode:
                        edit_mode = not edit_mode
                    else:
                        alarm_set = not alarm_set
                    if alarm_triggered:
                        alarm_set = False
                        alarm_triggered = False
            switch_menu_button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=switch_menu_isr)

    # Get current time from RTC
    (year, month, day, weekday, hour, minute, second, subseconds) = rtc.datetime()

    # Check if alarm should trigger
    if alarm_set and not alarm_triggered:
        if hour == alarm_time[0] and minute == alarm_time[1]:
            alarm_triggered = True
            edit_mode = False

    # Update pulse counter for blinking effect
    pulse_counter += 1
    show_pulse = (pulse_counter // 10) % 2  # Blink every 10 iterations

    # Draw alarm screen
    display.fill(0)
    display.text("Time: {:02d}:{:02d}:{:02d}".format(hour, minute, second), 0, 1, 1)
    
    # Display alarm time with pulsing effect
    if edit_mode:
        if editing_hours:
            # Pulse the hours digit
            if show_pulse:
                display.text("Alarm: {:02d}:{:02d}".format(alarm_time[0], alarm_time[1]), 0, 12 , 1)
            else:
                display.text("Alarm: __:{:02d}".format(alarm_time[1]), 0, 12, 1)
            display.text("Edit: HOURS", 0, 25, 1)
        else:
            # Pulse the minutes digit
            if show_pulse:
                display.text("Alarm: {:02d}:{:02d}".format(alarm_time[0], alarm_time[1]), 0, 12, 1)
            else:
                display.text("Alarm: {:02d}:__".format(alarm_time[0]), 0, 12, 1)
            display.text("Edit: MINUTES", 0, 25, 1)
    else:
        if time_mode:
            display.text("Time Change Mode On", 0, 20, 1)
        else:
            display.text("Alarm: {:02d}:{:02d}".format(alarm_time[0], alarm_time[1]), 0, 12, 1)
            display.text("Set: {}".format("ON" if alarm_set else "OFF"), 0, 25, 1)
    
    if alarm_triggered:
        display.fill(0)
        display.text("**ALARM!**", 0, 2, 1)
        led.duty_u16(30000)
    else:
        led.duty_u16(0)

    light_val = sensor_pin.read_u16()
    contrast_val = int(255 * (light_val/65535))
    display.contrast(contrast_val)
    display.show()
