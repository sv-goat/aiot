import json
import time
import requests

# Define the commands and sample args matching lab5's COMMANDS map
TEST_CASES = [
    ("screen_off", []),
    ("screen_on", []),
    ("display_time", []),
    # ("display_text", ["6 7"]),
    ("set_alarm", ["11", "31"]),
    ("display_location", []),
    # ("display_weather", []),
    # ("screen_off", [])
]


def do_post(host, port, payload, timeout=5):
    url = f"http://{host}:{port}/run"
    r = requests.post(url, json=payload, timeout=timeout)
    return r.status_code, r.text


def main():
    host = "10.206.21.168"
    port = 80
    delay = 5

    for name, test_args in TEST_CASES:
        payload = {"name": name, "args": test_args}
        print("-" * 60)
        print(f"Testing {name} with args={test_args}")
        print("Payload:", json.dumps(payload))

        try:
            code, body = do_post(host, port, payload)
            print("HTTP status:", code)
            print("Response:", body)
        except Exception as e:
            print("Request failed:", e)

        time.sleep(delay)

    print("\nTest run complete.")


if __name__ == "__main__":
    main()
