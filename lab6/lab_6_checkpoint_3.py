import urequests as requests
import network
import time


# Might need to change this if vm ip changes. 
url = "http://35.194.242.94:5000/data"  # include http://
fake_json = {"imu": [2, 4, 6]}

# Connect to WiFi

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

print("Inside main")
try:
    response = requests.post(url, json = fake_json)
    print("Status:", response.status_code)
    print("Response:", response.text)
    # optionally close if supported
except Exception as e:
    print("Error during POST:", e)
