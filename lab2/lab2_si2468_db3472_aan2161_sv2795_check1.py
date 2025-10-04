from machine import ADC, Pin, PWM
from time import sleep

light_sensor_input_port = 36
output_port = 15

light_sensor = ADC(Pin(light_sensor_input_port))

led = PWM(Pin(output_port), freq=1000)

light_sensor.width(ADC.WIDTH_12BIT)  

while True:
    reading = light_sensor.read()  # Read the analog value (0–4095)
    print("Light level:", reading)
    # clamp reading between 0 and 1023
    reading = max(0, min(768, reading))
    led.duty(reading)
    sleep(0.1)  # 1 sample per second
