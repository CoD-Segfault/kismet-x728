#!/bin/bash

# Instantiate DS1307 on the I2C bus
echo ds1307 0x68 > /sys/class/i2c-adapter/i2c-1/new_device

# Read time from RTC.
hwclock -s