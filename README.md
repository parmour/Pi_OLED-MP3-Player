# Pi_OLED-MP3-Player

A simple MP3 Player and Internet Radio Player using a Raspberry Pi, 6 buttons, and 1 OLED

All buttons are connected between gpios and gnd (1k resistors in series are usually recommended), OLED connected as shown. 

## schematic

![schematic](schematic.jpg)

6 button switches, PREVIOUS,PLAY,NEXT,VOLUME DOWN, VOLUME UP,SLEEP but they have multi purposes as shown.


At boot it will look for mp3 tracks in '/home/<<user>>/Music/artist name/album_name/tracks', 
and/or on USB sticks, under /media/<<user>>/usb_stick_name/artist name/album_name/tracks

To install copy Pi_OLED_MP3_player.py to /home/<<user>>

sudo apt-get install mplayer

sudo pip3 install mutagen

and then

 To install SSD1306 driver...
 
 git clone https://github.com/adafruit/Adafruit_Python_SSD1306.git
 
 cd Adafruit_Python_SSD1306
 
 sudo python setup.py install
 
 reboot



