#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2021 Craig Gowing

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Service to monitor and log the temperature of brewing and toggle heating,
basically an over-glorified thermostat. In future this will log within RRD
files and show real time stats and controls over HTTP.
"""

import re
import sys
import time
import RPi.GPIO as GPIO

FAIL_LIMIT = 5

class BeerMonitor:
    def __init__(self, low_temp, high_temp, heating_gpio, temp_device, log_file):
        self.low_temp = low_temp
        self.high_temp = high_temp
        self.heating_gpio = heating_gpio
        self.temp_device = temp_device
        self.log_file = log_file
        self.heating = False

    def run(self):
        try:
            temp_fails = 0
            GPIO.setmode(GPIO.BCM)
            # This is a HIGH type relay, so HIGH means the relay is in the NO state
            GPIO.setup(self.heating_gpio, GPIO.OUT, initial=GPIO.HIGH)
            sys.stdout.write("GPIO setup complete")
            while True:
                last_temp = self.read_temp()
                if last_temp is None:
                    temp_fails += 1
                    if temp_fails >= FAIL_LIMIT:
                        raise RuntimeError(f'Failed to read temperature after {FAIL_LIMIT} tries')
                    time.sleep(60)
                    continue
                self.temp_fails = 0
                if last_temp <= self.low_temp and not self.heating:
                    self.heating = True
                elif last_temp >= self.high_temp and self.heating:
                    self.heating = False
                self.set_heating(self.heating)
                open(self.log_file, 'a+').write(
                    f'{int(time.time())}, {last_temp}, {int(self.heating)}\n')
                time.sleep(60)
        except Exception as e:
            sys.stderr.write(f"Critical error, aborting: {e}\n")
            raise e
        finally:
            GPIO.cleanup(self.heating_gpio)

    def read_temp(self):
        try:
            raw_data = open(self.temp_device, 'r').read()
            temp = float(re.findall('t=([0-9]+)', raw_data)[0]) / 1000
        except Exception as e:
            sys.stderr.write(f"Error reading temperature: {e}\n")
            temp = None
        return temp

    def set_heating(self, enabled):
        current_state = GPIO.input(self.heating_gpio)
        if enabled:
            if current_state == GPIO.HIGH:
                sys.stdout.write("Changing heating to ON")
            GPIO.output(self.heating_gpio, GPIO.LOW)
        else:
            if current_state == GPIO.LOW:
                sys.stdout.write("Changing heating to OFF")
            GPIO.output(self.heating_gpio, GPIO.HIGH)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        prog='beerpi.py',
        description='Monitor brewing temperature and control heating')
    parser.add_argument('--low-temp', action='store', type=float, default=19.0)
    parser.add_argument('--high-temp', action='store', type=float, default=20.0)
    parser.add_argument('--heating-gpio', action='store', type=int, default=24)
    parser.add_argument('--temp-device', action='store', type=str,
                        default="/sys/bus/w1/devices/28-012033bc7ee2/w1_slave")
    parser.add_argument('--log-file', action='store', type=str,
                        default="templog.csv")
    args = parser.parse_args()

    beermonitor = BeerMonitor(args.low_temp, args.high_temp, args.heating_gpio,
                              args.temp_device, args.log_file)
    beermonitor.run()
