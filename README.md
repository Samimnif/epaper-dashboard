# E-Paper Home Dashboard
## Idea
Have an e-paper display at home that gives you some important daily info. For example:
* Garbage Collection Day
* OC Transpo next bus arrival time
* Weather and day highlights (Maybe? I don't need it lol)

> [!NOTE]  
> WORK IN PROGRESS

## Hardware
* [Raspberry Pi Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
* [7.3inch ACeP 7-Color E-Paper E-Ink Display Module, 800×480 Pixels](https://www.waveshare.com/7.3inch-e-Paper-HAT-F.htm)

## Setup
1. Setup your Raspberry pi zero with RaspiOS Lite
2. Follow WaveShare [Docs](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_(F)_Manual#Working_With_Raspberry_Pi) on setting up drivers for the 7.3 inch e-Paper hat F
```python
   sudo apt-get update
   sudo apt-get install python3-pip
   sudo apt-get install python3-pil
   sudo apt-get install python3-numpy
   sudo pip3 install RPi.GPIO
   sudo pip3 install spidev

   git clone https://github.com/waveshare/e-Paper.git
   cd e-Paper/RaspberryPi_JetsonNano/
```
3. Use the provided list of e-paper drivers to select the appropriate file and test file.

> [!NOTE]  
> Dashboard design Progress 
> ![Dashboard Layout](/img_doc/IMG_5402.jpeg)
> ![Raspberry PI Zero Connection](/img_doc/IMG_5403.jpeg)