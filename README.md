# E-Paper Home Dashboard
## Idea
Have an e-paper display at home that gives you some important daily info. For example:
* Garbage Collection Day
* OC Transpo next bus arrival time
* Weather and day highlights

> [!NOTE]  
> WORK IN PROGRESS

1. Setup your Raspberry pi zero with RaspiOS Lite
2. Follow WaveShare [Docs](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_(F)_Manual#Working_With_Raspberry_Pi) on setting up drivers for the 7.3 inch e-Paper hat F
```python
   sudo apt-get update
   sudo apt-get install python3-pip
   sudo apt-get install python3-pil
   sudo apt-get install python3-numpy
   sudo pip3 install RPi.GPIO
   sudo pip3 install spidev 
```
3. 