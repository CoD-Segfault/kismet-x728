#!/bin/bash

# Check if running as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root or with sudo"
  exit
fi

# Add Kismet repo
wget -O - https://www.kismetwireless.net/repos/kismet-release.gpg.key | apt-key add -
echo 'deb https://www.kismetwireless.net/repos/apt/release/buster buster main' > /etc/apt/sources.list.d/kismet.list

# Add Re4son-Kernel
echo "deb http://http.re4son-kernel.com/re4son/ kali-pi main" > /etc/apt/sources.list.d/re4son.list
wget -O - https://re4son-kernel.com/keys/http/archive-key.asc | apt-key add -

# Update repos, do a system upgrade, then install our software
apt update
apt dist-upgrade -y
apt install -y kalipi-kernel kalipi-bootloader kalipi-re4son-firmware \
    kismet gpsd gpsd-clients ntp python-smbus python-requests

# Add pi user to kismet group
usermod -a -G kismet pi

# change kismet service to use pi user and enable it
sed -i 's/root/pi' /lib/systemd/system/kismet.service
systemctl daemon-reload
systemctl enable kismet

# Create directory for Kismet logs, configure kismet to use it
mkdir -p /home/pi/kismetlogs/processed
chown -R pi:pi /home/pi/kismetlogs
echo "log_prefix=/home/pi/kismetlogs" >> /etc/kismet/kismet_site.conf 

# Enable GPS in kismet
echo "gps=gpsd:host=localhost,port=2947" >> /etc/kismet/kismet_site.conf 

# Enable i2c
raspi-config nonint go_i2c 0

# Enable RTC
echo rtc-ds1307 >> /etc/modprobe.d/rtc.conf
cp rtc.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable rtc
chmod +x /opt/kismet-x728/rtc.sh

# Enable X728 service
cp x728.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable x728

# Disable the systemd time service, as it interferes with ntpd
systemctl disable systemd-timesyncd

# copy ntpd and gpsd config files
cp gpsd /etc/default/gpsd
cp ntp.conf /etc/ntp.conf

# Enable ntpd and gpsd
systemctl enable ntp
systemctl enable gpsd

echo "Please reboot."