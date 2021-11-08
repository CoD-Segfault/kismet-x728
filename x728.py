#!/usr/bin/env python
import RPi.GPIO as GPIO
import time
import smbus
import os
import glob
import tarfile
import requests

wigle_api_name = ""
wigle_api_token = ""

upload_url = "https://api.wigle.net/api/v2/file/upload"

# Log file location including trailing /
kismet_log_directory = "/home/pi/kismetlogs/"

#version of board, 1 for 1.x or 2 for 2.x
x728_ver = 2

ups_I2C_address = 0x36          # I2C address of the battery charge controller

# Pi GPIO pins needed for power functionality
power_loss_detect_pin = 6       # Goes high on power loss
buzzer_pin = 20                 # Buzzer 
shutdown_pin = 5                # UPS sends signal to safe shutdown Pi 200-600ms for reboot, 600+ for power off
pi_on_pin = 12                  # Hold high while Pi is on, goes low after shutdown to signal to UPS
if x728_ver == 2:
    button_pin = 26             # Sends signal to UPS to indicate when safe shutdown is to occur 3+ seconds 
else:
    button_pin = 13             # Pin is 13 on 1.x and 26 on 2.x

# Setup all GPIO pins
GPIO.setmode(GPIO.BCM)
GPIO.setup(power_loss_detect_pin, GPIO.IN)
GPIO.setup(buzzer_pin, GPIO.OUT)
GPIO.setup(shutdown_pin, GPIO.IN)
GPIO.setup(pi_on_pin, GPIO.OUT)
GPIO.setup(button_pin, GPIO.OUT)

# Signal to UPS that Pi has booted
GPIO.output(pi_on_pin, 1)

# Swap endianness of 16-bit unsigned int
def swap16(x):
    return (((x <<  8) & 0xFF00) |
            ((x >>  8) & 0x00FF))

# Signal to UPS that we are shutting down, then issue power off
def safe_shutdown():
    GPIO.output(button_pin, 1)
    time.sleep(4)
    GPIO.output(button_pin, 0)
    os.system("sudo poweroff")

# Signal to UPS that we are rebooting, then reboot
def safe_reboot():
    GPIO.output(button_pin, 1)
    time.sleep(1.5)
    GPIO.output(button_pin, 0)
    os.system("sudo reboot")

# Stop kismet via systemd
def stop_kismet():
    os.system("sudo systemctl stop kismet")

# read kismet logs, convert them to Wigle format, upload if internet available
def process_kismet_logs():
    # find kismet logs and generate Wigle CSV format, move kismet logs to a processed folder
    log_files = glob.glob(kismet_log_directory + "/*.kismet")
    for file in log_files:
        print(file)
        os.system("kismetdb_to_wiglecsv --in " + file + " --out " + file + ".csv")
        os.system("mv " + file + " " + kismet_log_directory + "/processed")
    
    # TGZ up all Wigle CSV files
    wigle_csv_files = glob.glob(kismet_log_directory + "/*.csv")
    if(len(wigle_csv_files) > 0):
        tar = tarfile.open(kismet_log_directory + time.strftime("%Y%m%d%H%M%S") + ".tgz", "w:gz")
        for file in wigle_csv_files:
            tar.add(file)
            os.remove(file)
        tar.close()
    
    # attempt to upload any TGZ files, deleting if successful
    tgz_files = glob.glob(kismet_log_directory + "*.tgz")
    for file in tgz_files:
        filelist = {'file': (file, open(file, 'rb'))}
        try:
            r = requests.post(upload_url, auth=(wigle_api_name, wigle_api_token), files=filelist)
            if r.status_code == requests.codes.ok:
                filelist.clear()
                os.remove(file)
        except requests.exceptions.RequestException as e:
            print(e)

# Enable reading from I2C
bus = smbus.SMBus(1)            # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)

while(True):
    # Check for power loss and act accordingly.
    if GPIO.input(power_loss_detect_pin):
        GPIO.output(buzzer_pin, 1)
        time.sleep(0.25)
        GPIO.output(buzzer_pin, 0)
        stop_kismet()
        process_kismet_logs()
        safe_shutdown()
    
    # Check for signal from the UPS.  Triggered from the button. Will send a
    # roughly 500ms pulse for a reboot, or 50s (in my testing) for shutdown
    if GPIO.input(shutdown_pin):
        start_time = time.time()
        while(GPIO.input(shutdown_pin)):
            end_time = time.time()
        pressed_time = end_time - start_time
        pressed_ms = round(pressed_time * 1000)
        if pressed_ms < 600:
            safe_reboot()
        else:
            safe_shutdown()

    time.sleep(0.2)

