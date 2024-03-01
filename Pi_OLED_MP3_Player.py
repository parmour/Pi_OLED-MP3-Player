#!/usr/bin/env python3

"""Copyright (c) 2023
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
SOFTWARE."""

from gpiozero import Button
import glob
import subprocess
import os, sys
import time
import datetime
import random
from random import shuffle
from mutagen.mp3 import MP3
import alsaaudio
from signal import signal, SIGTERM, SIGHUP, pause

# To install SSD1306 driver...
# git clone https://github.com/adafruit/Adafruit_Python_SSD1306.git
# cd Adafruit_Python_SSD1306
# sudo python setup.py install
#
# Enable I2C on Pi. Pi Menu > Preferences > RPI Configuration > Interfaces > I2C
# reboot

import Adafruit_SSD1306
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

version  = "1.04"

# set default variables (saved in config_file and overridden at future startups)
MP3_Play     = 0    # set to 1 to start playing MP3s at boot, else 0
radio        = 0    # set to 1 to start playing Radio at boot, else 0
radio_stn    = 0    # selected radio station at startup 
shuffled     = 0    # 0 = Unshuffled, 1 = Shuffled
album_mode   = 1    # set to 1 for Album Mode, will play an album then stop
gapless      = 0    # set to 1 for gapless play
volume       = 50   # range 0 - 100
Track_No     = 0

# variables set once
use_USB      = 0    # set to 0 if you ONLY use /home/pi/Music/... on SD card
usb_timer    = 6   # seconds to find USB present
sleep_timer  = 0    # sleep_timer timer in minutes, use 15,30,45,60 etc...set to 0 to disable
sleep_shutdn = 0    # set to 1 to shutdown Pi when sleep times out
Disp_timer   = 60   # Display timeout in seconds, set to 0 to disable
show_clock   = 0    # set to 1 to show clock, only use if on web or using RTC
gaptime      = 2    # set pre-start time for gapless, in seconds
myUsername   = "philip"   # 

Radio_Stns = ["Radio Paradise Rock","http://stream.radioparadise.com/rock-192",
              "Radio Paradise Main","http://stream.radioparadise.com/mp3-320",
              "Radio Paradise Mellow","http://stream.radioparadise.com/mellow-192",
              "Radio Caroline","http://sc6.radiocaroline.net:10558/"]

# GPIO BUTTONS GPIO BCM numbers (Physical pin numbers)

PREV   = 20 # (38) PREVIOUS TRACK  (whilst playing) / PREV ALBUM (whilst stopped) / PREV ARTIST (HOLD for 5 secs whilst stopped) 
PLAY   = 12 # (32) PLAY / STOP / HOLD for 5 seconds for RADIO 
NEXT   = 7  # (26) NEXT TRACK (whilst playing) / NEXT ALBUM (whilst stopped) / NEXT ARTIST (HOLD for 5 secs whilst stopped)
SLEEP  = 25 # (22) Set SLEEP time, HOLD for 20 seconds to SHUTDOWN, set ALBUM MODE whilst stopped.
VOLDN  = 16 # (36) Adjust volume DOWN whilst playing, set GAPLESS ON/OFF whilst stopped
VOLUP  = 8  # (24) Adjust volume UP whilst playing, set RANDOM ON/OFF whilst stopped


# check config file exists, if not then write default values
config_file = "OLEDconfig.txt"
if not os.path.exists(config_file):
    defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)

# read config file
config = []
with open(config_file, "r") as file:
   line = file.readline()
   while line:
      config.append(line.strip())
      line = file.readline()
config = list(map(int,config))

MP3_Play   = config[0]
radio      = config[1]
radio_stn  = config[2]
shuffled   = config[3]
album_mode = config[4]
volume     = config[5]
gapless    = config[6]
Track_No   = config[7]

if Track_No < 0:
    Track_No = 0

# setup oled
# 128x32 display with hardware I2C:
RST = None
disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)
disp.begin()
disp.clear()
disp.display()
width  = disp.width
height = disp.height
image  = Image.new('1', (width, height))
draw = ImageDraw.Draw(image)
draw.rectangle((0,0,width,height), outline=0, fill=0)
top = -2
font = ImageFont.load_default()

# read radio_stns.txt - format: Station Name,Station URL
if os.path.exists ("radio_stns.txt"): 
    with open("radio_stns.txt","r") as textobj:
        line = textobj.readline()
        while line:
           if line.count(",") == 1:
               a,b = line.split(",")
               Radio_Stns.append(a)
               Radio_Stns.append(b.strip())
           line = textobj.readline()

# setup GPIO
buttonPREV  = Button(PREV)
buttonPLAY  = Button(PLAY)
buttonNEXT  = Button(NEXT)
buttonVOLDN = Button(VOLDN)
buttonVOLUP = Button(VOLUP)
buttonSLEEP = Button(SLEEP)

# initialise parameters
old_album   = 0
old_artist  = 0
titles      = [0,0,0,0,0,0,0]
itles       = [0,0,0,0,0,0,0]
sleep_timer = sleep_timer * 60
freedisk    = ["0","0","0","0"]
old_secs    = "00"
old_secs2   = "00"
Disp_on     = 1
album       = 0
stimer      = 0
ctracks     = 0
cplayed     = 0
stopped     = 0
atimer      = time.monotonic()
played_pc   = 0
synced      = 0
reloading   = 0
msg1        = "MP3 Player: v" + version
msg2        = ""
msg3        = ""
msg4        = ""
abort_sd    = 1
usb_found   = 0

# find username
h_user  = []
h_user.append(myUsername)   # os.getlogin() not always working when script run automatically

def getTrack(trackNum):
    global tracks
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[trackNum].split("/")
    trackData = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
    return trackData

def display():
    global image,top,msg1,msg2,msg3,msg4,width,height,font
    # Display image.
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((0, top + 0), msg1,  font=font, fill=255)
    draw.text((0, top + 8), msg2,  font=font, fill=255)
    draw.text((0, top + 16),msg3,  font=font, fill=255)
    draw.text((0, top + 24),msg4,  font=font, fill=255)
    disp.image(image)
    disp.display()

display()
time.sleep(2)
stop = 0
def reload():
  global tracks,x,top,msg1,msg2,Track_No,stop
  if stop == 0:
    tracks  = []
    msg1 = "Tracks: " + str(len(tracks))
    msg2 = "Reloading tracks... "
    display()
    usb_tracks  = glob.glob("/media/" + h_user[0] + "/*/*/*/*.mp3")
    sd_tracks = glob.glob("/home/" + h_user[0] + "/Music/*/*/*.mp3")
    titles = [0,0,0,0,0,0,0]
    if len(sd_tracks) > 0:
      for xx in range(0,len(sd_tracks)):
        titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = sd_tracks[xx].split("/")
        track = titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2] + "/" + titles[3]
        tracks.append(track)
    if len(usb_tracks) > 0:
      for xx in range(0,len(usb_tracks)):
        titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = usb_tracks[xx].split("/")
        track = titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2] + "/" + titles[3]
        tracks.append(track)
    if len(tracks) > 0:
        tracks.sort()
    with open('tracks.txt', 'w') as f:
        for item in tracks:
            f.write("%s\n" % item)
    msg1 = ("Tracks: " + str(len(tracks)))
    Track_No = 0
    defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)
    display()
    if len(tracks) == 0:
        msg1 = "Tracks: " + str(len(tracks))
        msg2 = "Stopped Checking"
        display()
        stop = 1
    time.sleep(1)


def loadTrackDictionaries():
    global tracks, albumDictionary, artistDictionary, albumTuple, artistTuple
    albumTuple = ()    #   list of all albums in order    Because album names might not be unique, format is "AlbumName - Artist"
    artistTuple = ()   #   list of all artists in order
    albumDictionary = {}   #  key is album ("AlbumName - Artist"), value is (first track number, last track number)
    artistDictionary = {}   #  key is artist, value is (first track number, last track number)
    currentArtist = ""
    currentArtistFirst = 0
    currentArtistLast = 0
    currentAlbum = ""
    currentAlbumFirst = 0
    currentAlbumLast = 0
    for trackNum in range(0,len(tracks)):
        ( artist, album, song, path1, path2, path3 ) = tracks[trackNum].split("/")
        uniqAlbum = album + " - " + artist   # Because album names might not be unique, format is "AlbumName - Artist"
        if artist not in artistTuple:
            artistTuple += ( artist, )
        if uniqAlbum not in albumTuple:
            albumTuple += ( uniqAlbum, )
        if not currentArtist:
            currentArtist = artist
        elif artist != currentArtist:
            currentArtistLast = trackNum - 1
            if currentArtist not in artistDictionary.keys():
                artistDictionary[currentArtist] = ( currentArtistFirst, currentArtistLast)
            currentArtist = artist
            currentArtistFirst = trackNum
            currentArtistLast = trackNum
        if not currentAlbum:
            currentAlbum = uniqAlbum
        elif uniqAlbum != currentAlbum:
            currentAlbumLast = trackNum - 1
            if currentAlbum not in albumDictionary.keys():
                albumDictionary[currentAlbum] = ( currentAlbumFirst, currentAlbumLast)
            currentAlbum = uniqAlbum
            currentAlbumFirst = trackNum
            currentAlbumLast = trackNum
    currentArtistLast = trackNum
    if currentArtist not in artistDictionary.keys():  # process the last artist
        artistDictionary[currentArtist] = ( currentArtistFirst, currentArtistLast )            
    currentAlbumLast = trackNum
    if currentAlbum not in albumDictionary.keys():  # process the last album
        albumDictionary[currentAlbum] = ( currentAlbumFirst, currentAlbumLast)   

def getArtistAlbumSongNames(trackNum):
    global tracks
    ( artist, album, song, path1, path2, path3 ) = tracks[trackNum].split("/")
    return ( artist, album, song )

def getAlbumStartFinish(trackNum):
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    uniqAlbum = album + " - " + artist
    ( currentAlbumFirst, currentAlbumLast) = albumDictionary[uniqAlbum]
    return ( currentAlbumFirst, currentAlbumLast)

def getArtistStartFinish(trackNum):
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    ( currentArtistFirst, currentArtistLast) = artistDictionary[artist]
    return ( currentArtistFirst, currentArtistLast)

def getRemainingAlbumTracks(trackNum):
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    numRemainingTracks = currentAlbumLast - trackNum
    return numRemainingTracks

def getRemainingAlbumTime(trackNum):
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    timeRemaining = 0
    for trackCounter in range(trackNum,currentAlbumLast):
        trackDetails = getTrack(trackCounter)
        audio = MP3(trackDetails)
        timeRemaining += audio.info.length
    return timeRemaining

def goToNextAlbum(trackNum):
    global tracks
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    nextAlbumStart = currentAlbumLast + 1
    if nextAlbumStart > len(tracks):
        nextAlbumStart = 0
    return nextAlbumStart

def goToNextArtist(trackNum):
    global tracks
    ( currentArtistFirst, currentArtistLast) = getArtistStartFinish(trackNum)
    nextArtistStart = currentArtistLast + 1
    if nextArtistStart > len(tracks):
        nextArtistStart = 0
    return nextArtistStart

def goToPrevAlbum(trackNum):
    global tracks
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    prevAlbumEnd = currentAlbumFirst - 1
    if prevAlbumEnd > 0:
        ( prevAlbumFirst, prevAlbumLast) = getAlbumStartFinish(prevAlbumEnd)
    else:
        prevAlbumFirst = 0
    return prevAlbumFirst

def goToPrevArtist(trackNum):
    global tracks
    ( currentArtistFirst, currentArtistLast) = getArtistStartFinish(trackNum)
    prevArtistEnd = currentArtistFirst - 1
    if prevArtistEnd > 0:
        ( prevArtistFirst, prevArtistLast) = getArtistStartFinish(prevArtistEnd)
    else:
        prevArtistFirst = 0
    return prevArtistFirst

def getSongDetails(trackNum):
    ( artist, album, song ) = getArtistAlbumSongNames(Track_No)
    out1 = artist[0:19]
    out2 = album[0:19]
    out3 = song[0:19]
    try:
        if int(song[0:2]) > 0:
            out3 = song[3:22]
    except:
        pass
    return ( out1, out2, out3)


def Set_Volume():
    global mixername,m,msg1,msg2,msg3,msg4,MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless
    msg1 = "Set Volume.. " + str(volume)
    msg2 = ""
    msg3 = ""
    msg4 = ""
    while buttonVOLUP.is_pressed:
        volume +=1
        volume = min(volume,100)
        m.setvolume(volume)
        msg1 = "Set Volume.. " + str(volume)
        display()
        os.system("amixer -D pulse sset Master " + str(volume) + "%")
        if mixername == "DSP Program":
            os.system("amixer set 'Digital' " + str(volume + 107))
    while buttonVOLDN.is_pressed:
        volume -=1
        volume = max(volume,0)
        m.setvolume(volume)
        msg1 = "Set Volume.. " + str(volume)
        display()
        os.system("amixer -D pulse sset Master " + str(volume) + "%")
        if mixername == "DSP Program":
            os.system("amixer set 'Digital' " + str(volume + 107))
    defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)

def status():
    global txt,shuffled,gapless,album_mode,sleep_timer
    txt = " "
    if shuffled == 1:
        txt +="R"
    else:
        txt +=" "
    if gapless == 1:
        txt +="G"
    else:
        txt +=" "
    if album_mode == 1:
        txt +="A"
    else:
        txt +=" "
    if sleep_timer > 0:
        txt +="S"
    else:
        txt +=" "

# read previous usb free space of upto 4 usb devices, to see if usb data has changed
if not os.path.exists('freedisk.txt'):
    with open("freedisk.txt", "w") as f:
        for item in freedisk:
            f.write("%s\n" % item)
freedisk = []            
with open("freedisk.txt", "r") as file:
    line = file.readline()
    while line:
         freedisk.append(line.strip())
         line = file.readline()
         
# check if SD Card ~/Music has changed
if not os.path.exists('freeSD.txt'):
    with open("freeSD.txt", "w") as f:
            f.write("0")
with open("freeSD.txt", "r") as file:
    line = file.readline()

def get_dir_size(dir_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(dir_path):
        for file in filenames:
            file_path = os.path.join(dirpath, file)
            if not os.path.islink(file_path):
                total_size += os.path.getsize(file_path)
    return total_size

total_size = get_dir_size("/home/" +  h_user[0] + "/Music")
if line != str(total_size):
    with open("freeSD.txt", "w") as f:
        f.write(str(total_size))
    reloading = 1

# load MP3 tracks
tracks  = []
if not os.path.exists('tracks.txt') and stop == 0:
    reload()
else:
    with open("tracks.txt", "r") as file:
        line = file.readline()
        while line:
             tracks.append(line.strip())
             line = file.readline()


msg1 = "Tracks: " + str(len(tracks))
display()

# check if USB mounted and find USB storage
if use_USB == 1:
    start = time.monotonic()
    msg1 = ("Checking for USB")
    display()
    while time.monotonic() - start < usb_timer:
        usb = glob.glob("/media/" +  h_user[0] + "/*")
        usb_found = len(usb)
        msg2 = "Found: " + str(usb_found) + " USBs"
        msg3 = str(int(usb_timer -(time.monotonic() - start)))
        display()
        time.sleep(1)
    msg2 = ""
    msg3 = ""
    display()
    if usb_found > 0:
        # check if usb contents have changed, if so then reload tracks
        free = ["0","0","0","0"]
        for xy in range(0,len(usb)):
            st3 = os.statvfs(usb[xy])
            free[xy] = str((st3.f_bavail * st3.f_frsize)/1100000)
        for xy in range(0,3):
            if str(free[xy]) != freedisk[xy]:
                with open("freedisk.txt", "w") as f:
                    for item in free:
                        f.write("%s\n" % item)
                reloading = 1
    else:
        freedisk = ["0","0","0","0"]
        with open("freedisk.txt", "w") as f:
            for item in freedisk:
                f.write("%s\n" % item)
        msg2 = "No USB Found !!"
        display()
        sd_tracks = glob.glob("/home/" + h_user[0] + "/Music/*/*/*.mp3")
        time.sleep(2)
        if len(sd_tracks) != len(tracks):
            reloading = 1
        msg2 = ""
        display()

if reloading == 1 and stop == 0:
    reload()



# check for audio mixers
if len(alsaaudio.mixers()) > 0:
    for mixername in alsaaudio.mixers():
        if str(mixername) == "PCM" or str(mixername) == "DSP Program" or str(mixername) == "Master" or str(mixername) == "Capture" or str(mixername) == "Headphone" or str(mixername) == "HDMI":
            m = alsaaudio.Mixer(mixername)
        else:
            m = alsaaudio.Mixer(alsaaudio.mixers()[0])
    m.setvolume(volume)
    os.system("amixer -D pulse sset Master " + str(volume) + "%")
    if mixername == "DSP Program":
        os.system("amixer set 'Digital' " + str(volume + 107))
        

# disable Radio Play if MP3 Play set
if MP3_Play == 1:
    radio = 0
    
# wait for internet connection
if radio == 1:
    msg1 = "Waiting for Radio..."
    display()
    time.sleep(10)
    q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] ,shell=False)
    msg1 = (Radio_Stns[radio_stn])
    msg2 = ""
    display()

# try reloading tracks if one selected not found
if len(tracks) > 0:
    track = getTrack(Track_No)
    if not os.path.exists (track) and usb_found > 0 and stop == 0:
        reload()

# populate albumDictionary, artistDictionary, albumTuple, artistTuple
loadTrackDictionaries()  

if album_mode == 1 and len(tracks) > 0:
    # determine album length and number of tracks
    cplayed = 0
    shuffled = 0
    if album_mode == 1:
        ctracks = getRemainingAlbumTracks(Track_No)
        stimer = getRemainingAlbumTime(Track_No) 


if album_mode == 0:
    track_n = str(Track_No + 1) + "     "
else:
    track_n = "1/" + str(ctracks) + "       "

status()
    
if shuffled == 1 and gapless == 0:
    gap = 0
    shuffle(tracks)
elif shuffled == 0 and gapless == 0:
    gap = 0
elif shuffled == 1 and gapless != 0:
    gap = gaptime
    shuffle(tracks)
elif shuffled == 0 and gapless != 0:
    gap = gaptime

if len(tracks) > 0:
    ( artist, album, song ) = getArtistAlbumSongNames(Track_No)

sleep_timer_start = time.monotonic()
Disp_start        = time.monotonic()
timer2            = time.monotonic()
sync_timer        = time.monotonic()
xt                = 0

# check if clock synchronised
if os.path.exists ("/run/shm/sync.txt"):
    os.remove("/run/shm/sync.txt")
os.system("timedatectl >> /run/shm/sync.txt")
# read sync.txt file
try:
    sync = []
    with open("/run/shm/sync.txt", "r") as file:
        line = file.readline()
        while line:
            sync.append(line.strip())
            line = file.readline()
    if sync[4] == "System clock synchronized: yes":
        synced = 1
    else:
        synced = 0
except:
    pass

while True:
    # loop while stopped
    while MP3_Play == 0 and radio == 0:
        # check if clock synchronised
        if time.monotonic() - sync_timer > 30:
            sync_timer = time.monotonic()
            if os.path.exists ("/run/shm/sync.txt"):
                os.remove("/run/shm/sync.txt")
            os.system("timedatectl >> /run/shm/sync.txt")
            try:
                sync = []
                with open("/run/shm/sync.txt", "r") as file:
                    line = file.readline()
                    while line:
                        sync.append(line.strip())
                        line = file.readline()
                if sync[4] == "System clock synchronized: yes":
                    synced = 1
                else:
                    synced = 0
            except:
                pass
            
        # display Artist / Album / Track names
        if time.monotonic() - timer2 > 3 and Disp_on == 1 and len(tracks) > 0:
            ( msg2, msg3, msg4) = getSongDetails(Track_No)
            timer2 = time.monotonic()
            if xt < 2:
                if album_mode == 0:
                    track_n = str(Track_No + 1) + "     "
                else:
                    track_n = "1/" + str(ctracks) + "       "
                msg1 = "Play: " + str(track_n)[0:5]  
            elif xt == 2:
                status()
                msg1 = "Status...  "  +  txt
            elif xt == 3 and show_clock == 1 and synced == 1:
                now = datetime.datetime.now()
                clock = now.strftime("%H:%M:%S")
                msg1 = clock
            elif xt == 4:
                msg1 = "Volume: " + str(volume)
            elif xt == 5 and sleep_timer != 0:
                time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                msg1 = "SLEEP: " + str(time_left) + " mins"
            else:
                xt +=1
            display()
            xt +=1
            if xt > 5:
                xt = 0

        # display clock (if enabled and synced)
        if show_clock == 1 and Disp_on == 0 and synced == 1 and stopped == 0 and abort_sd == 1:
            now = datetime.datetime.now()
            clock = now.strftime("%H:%M:%S")
            secs = now.strftime("%S")
            t = ""
            for r in range (0,random.randint(0,10)):
                t += " "
            clock = t + clock
            if secs != old_secs2 :
              vp = random.randint(0,3)
              msg1 = ""
              msg2 = ""
              msg3 = ""
              msg4 = ""
              if vp == 0:
                msg1 = clock
              elif vp == 1:
                msg2 = clock
              elif vp == 2:
                msg3 = clock
              elif vp == 3:
                msg4 = clock
              display()
              old_secs2 = secs

        # DISPLAY OFF timer
        if time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1:
            msg1 = ""
            msg2 = ""
            msg3 = ""
            msg4 = ""
            Disp_on = 0
            display()
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    msg2 = "SHUTDOWN in " + str(t)
                else:
                    msg2 = "STOPPING in " + str(t)
                display()
                if buttonSLEEP.is_pressed or buttonPLAY.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    msg1 = "SHUTTING DOWN..."
                else:
                    msg1 = "STOPPING........"
                msg2 = ""
                msg3 = ""
                msg4 = ""
                display()
                time.sleep(3)
                msg1 = ""
                display()
                sleep_timer = 0 
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
            else:
                status()
                if album_mode == 0:
                    track_n = str(Track_No + 1) + "     "
                else:
                    track_n = "1/" + str(ctracks) + "       "
                msg1 = "Play.." + str(track_n)[0:5]
                display()
            Disp_start = time.monotonic()
            
        # check for PLAY key
        if buttonPLAY.is_pressed:
            stopped = 0
            Disp_on = 1
            Disp_start = time.monotonic()
            timer1 = time.monotonic()
            album = 0
            msg2 = "HOLD 5s for RADIO"
            msg3 = ""
            msg4 = ""
            display()
            time.sleep(0.5)
            sleep_timer = 0
            while buttonPLAY.is_pressed and time.monotonic() - timer1 < 5:
                pass
            if time.monotonic() - timer1 < 5 and len(tracks) > 0:
                # determine album length and number of tracks
                cplayed = 0
                if album_mode == 1:
                    ctracks = getRemainingAlbumTracks(Track_No)
                    stimer = getRemainingAlbumTime(Track_No) 
                atimer = time.monotonic()
                MP3_Play = 1
                radio    = 0
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
            else:
                msg2 = ""
                msg3 = ""
                msg4 = ""
                q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
                time.sleep(0.05)
                msg1 = (Radio_Stns[radio_stn])
                display()
                rs = Radio_Stns[radio_stn]
                while buttonPLAY.is_pressed:
                    pass
                time.sleep(1)
                radio    = 1
                MP3_Play = 0
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                
        # check NEXT ALBUM / ARTIST key
        if buttonNEXT.is_pressed and len(tracks) > 1:
            Disp_on = 1
            time.sleep(0.2)
            Track_No = goToNextAlbum(Track_No)
            ctracks = getRemainingAlbumTracks(Track_No)
            ( msg2, msg3, msg4) = getSongDetails(Track_No)
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play:" + str(track_n)[0:5] 
            display()
            timer3 = time.monotonic()
            album = 1
            while buttonNEXT.is_pressed:
                # NEXT ARTIST if pressed > 2 seconds
                if time.monotonic() - timer3 > 2:
                    if buttonSLEEP.is_pressed == 0:
                        Track_No = goToNextArtist(Track_No)
                    else:
                        for doAgain in range(0,5):   # skip forward 5 artists at a time
                            Track_No = goToNextArtist(Track_No)
                    ctracks = getRemainingAlbumTracks(Track_No)
                    ( msg2, msg3, msg4) = getSongDetails(Track_No)
                    if album_mode == 0:
                        track_n = str(Track_No + 1) + "     "
                    else:
                        track_n = "1/" + str(ctracks) + "       "
                    msg1 = "Play:" + str(track_n)[0:5] 
                    display()
                    time.sleep(0.5)

            defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
            with open(config_file, 'w') as f:
                for item in defaults:
                    f.write("%s\n" % item)
            Disp_start = time.monotonic()
            timer2 = time.monotonic()
                        
        # check for VOLUP  key
        if buttonVOLUP.is_pressed and Disp_on == 0:
            Disp_on = 1
            Disp_start = time.monotonic()
            status()
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play.." + str(track_n)[0:5]
            time.sleep(0.5)
            timer2 = time.monotonic()
        elif buttonVOLUP.is_pressed:
            time.sleep(0.5)
            timer1 = time.monotonic()
            while buttonVOLUP.is_pressed and time.monotonic() - timer1 < 2:
                pass
            if time.monotonic() - timer1 < 1:
                msg2 = ""
                msg3 = ""
                msg4 = ""
                if shuffled == 0:
                    shuffled = 1
                    #shuffle(tracks)
                    #Track_No = 0
                    album_mode = 0
                    track_n  = str(Track_No + 1) + "     "
                    msg2 = "Random Mode ON "
                    
                else:
                    shuffled = 0
                    msg2 = "Random Mode OFF "
                    ####
                if album_mode == 1:
                    ctracks = getRemainingAlbumTracks(Track_No)
                    track_n = "1/" + str(ctracks) + "       "
                else:
                    track_n  = str(Track_No) + "     
                display()
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                time.sleep(1)
                timer2 = time.monotonic()
                xt = 2
            else:                  
                Set_Volume()

            status()
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play.." + str(track_n)[0:5] 
            display()
            Disp_start = time.monotonic()
            timer2 = time.monotonic()

        # check for VOLDN  key
        if  buttonVOLDN.is_pressed and Disp_on == 0:
            Disp_on = 1
            Disp_start = time.monotonic()
            status()
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play.." + str(track_n)[0:5] 
            time.sleep(0.5)
            timer2 = time.monotonic()
        elif buttonVOLDN.is_pressed:
            time.sleep(0.5)
            timer1 = time.monotonic()
            timer = time.monotonic()
            while buttonVOLDN.is_pressed and time.monotonic() - timer < 2:
                pass
            if time.monotonic() - timer < 1:
                if gapless == 0:
                    gap = gaptime
                    gapless = 1
                    msg2 = "Gapless ON"
                    msg3 = ""
                    msg4 = ""
                    display()
                    time.sleep(1)
                else:
                    gap = 0
                    gapless = 0
                    msg2 = "Gapless OFF"
                    msg3 = ""
                    msg4 = ""
                    display()
                    time.sleep(1)
                status()
                if album_mode == 0:
                    track_n = str(Track_No + 1) + "     "
                else:
                    track_n = "1/" + str(ctracks) + "       "
                msg1 = "Track.." + str(track_n)[0:5]
                display()
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                time.sleep(0.5)
                timer2 = time.monotonic()
                xt = 2
            else:                  
                Set_Volume()
                timer2 = time.monotonic()
                
        # check for PREVIOUS ALBUM key 
        if  buttonPREV.is_pressed and len(tracks) > 1:
            Disp_on = 1
            Track_No = goToPrevAlbum(Track_No)
            ctracks = getRemainingAlbumTracks(Track_No)
            ( msg2, msg3, msg4) = getSongDetails(Track_No)
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play:" + str(track_n)[0:5] 
            time.sleep(0.05)
            display()
            time.sleep(0.05)
            timer3 = time.monotonic()
            album = 1
            while buttonPREV.is_pressed:
                # PREVIOUS ARTIST if pressed > 2 seconds
                if time.monotonic() - timer3 > 2:
                    Track_No = goToPrevArtist(Track_No)
                    ctracks = getRemainingAlbumTracks(Track_No)
                    ( msg2, msg3, msg4) = getSongDetails(Track_No)
                    if album_mode == 0:
                        track_n = str(Track_No + 1) + "     "
                    else:
                        track_n = "1/" + str(ctracks) + "       "
                    msg1 = "Play:" + str(track_n)[0:5] 
                    display()
                    time.sleep(0.5)

            defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
            with open(config_file, 'w') as f:
                for item in defaults:
                    f.write("%s\n" % item)
            Disp_start = time.monotonic()
            timer2 = time.monotonic()
            
        # check for SLEEP key
        if  buttonSLEEP.is_pressed and Disp_on == 0:
            Disp_on = 1
            Disp_start = time.monotonic()
            status()
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play.." + str(track_n)[0:5]
            time.sleep(0.5)
            timer2 = time.monotonic()
        elif buttonSLEEP.is_pressed:
            timer1 = time.monotonic()
            while buttonSLEEP.is_pressed and time.monotonic() - timer1 < 2:
                pass
            if time.monotonic() - timer1 < 1:
                if album_mode == 0:
                    album_mode = 1
                    shuffled    = 0
                    msg2 = "Album Mode ON "
                    msg3 = ""
                    msg4 = ""
                    Track_No = goToNextAlbum(Track_No)
                    ctracks = getRemainingAlbumTracks(Track_No)
                    stimer = getRemainingAlbumTime(Track_No) 
                    track_n = str(cplayed) + "/" + str(ctracks) + "       "
                else:
                    album_mode = 0
                    msg2 = "Album Mode OFF "
                    msg3 = ""
                    msg4 = ""
                    track_n  = str(Track_No) + "     "
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                display()
                time.sleep(1)

            else:    
                sleep_timer +=900
                if sleep_timer > 7200:
                    sleep_timer = 0
                sleep_timer_start = time.monotonic()
                msg1 = "Set SLEEP.. " + str(int(sleep_timer/60))
                msg2 = "HOLD for 20 to SHUTDOWN "
                msg3 = ""
                msg4 = ""
                display()
                time.sleep(0.25)
                while buttonSLEEP.is_pressed:
                    sleep_timer +=900
                    if sleep_timer > 7200:
                         sleep_timer = 0
                    sleep_timer_start = time.monotonic()
                    msg1 = "Set SLEEP.. " + str(int(sleep_timer/60))
                    display()
                    time.sleep(1)
                    if time.monotonic() - timer1 > 10:
                        msg2 = "SHUTDOWN in " + str(20-int(time.monotonic() - timer1))
                        display()
                    if time.monotonic() - timer1 > 20:
                        # shutdown if pressed for 20 seconds
                        msg1 = "SHUTTING DOWN..."
                        msg2 = ""
                        msg3 = ""
                        msg4 = ""
                        display()
                        time.sleep(2)
                        msg1 = ""
                        display()
                        MP3_Play = 0
                        radio = 0
                        time.sleep(1)
                        os.system("sudo shutdown -h now")
            status()
            if album_mode == 0:
                track_n = str(Track_No + 1) + "     "
            else:
                track_n = "1/" + str(ctracks) + "       "
            msg1 = "Play.." + str(track_n)[0:5]
            display()
            timer2 = time.monotonic()
            xt = 2
            
    # loop while playing Radio
    while radio == 1:
        time.sleep(0.2)
        # check if clock synchronised
        if time.monotonic() - sync_timer > 60:
            sync_timer = time.monotonic()
            if os.path.exists ("/run/shm/sync.txt"):
                os.remove("/run/shm/sync.txt")
            os.system("timedatectl >> /run/shm/sync.txt")
            try:
                sync = []
                with open("/run/shm/sync.txt", "r") as file:
                    line = file.readline()
                    while line:
                        sync.append(line.strip())
                        line = file.readline()
                if sync[4] == "System clock synchronized: yes":
                    synced = 1
                else:
                    synced = 0
            except:
                pass
        # DISPLAY OFF timer
        if time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1:
            msg1 = ""
            msg2 = ""
            msg3 = ""
            msg4 = ""
            Disp_on = 0
            display()
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            Disp_on = 1
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    msg2 = "SHUTDOWN in " + str(t)
                    display()
                else:
                    msg2 = "STOPPING in " + str(t)
                    display()
                if buttonSLEEP.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    msg1 = "SHUTTING DOWN..."
                    display()
                else:
                    msg1 = "STOPPING........"
                display()
                msg2 = ""
                time.sleep(1)
                msg1 = ""
                display()
                q.kill()
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
                sleep_timer = 0
                time.sleep(1)
                stopped = 1
                radio = 0
            Disp_start = time.monotonic()
            
        # display sleep_timer time left and clock (if enabled and synced)
        now = datetime.datetime.now()
        clock = now.strftime("%H:%M:%S")
        secs = now.strftime("%S")
        time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
        msg1 = Radio_Stns[radio_stn]
        if sleep_timer > 0:
            msg3 = "Shutdown: " + str(time_left) + "mins"
        if show_clock == 1 and synced == 1:
            msg2 = "      " + clock
        t = ""
        for r in range (0,random.randint(0,10)):
            t += " "
        clock = t + clock
        if Disp_on == 1:
            display()
        if show_clock == 1 and Disp_on == 0 and synced == 1:
            if secs != old_secs:
                if sleep_timer > 0:
                    clock = clock + " " + str(time_left)
                vp = random.randint(0,3)
                msg1 = ""
                msg2 = ""
                msg3 = ""
                msg4 = ""
                if vp == 0:
                    msg1 = clock
                elif vp == 1:
                    msg2 = clock
                elif vp == 2:
                    msg3 = clock
                elif vp == 3:
                    msg4 = clock
                display()
                old_secs = secs
            
         # check for VOLDN  key
        if  buttonVOLDN.is_pressed :
            Disp_on = 1
            Disp_start = time.monotonic()
            display()
            Set_Volume()
            time.sleep(0.5)
            timer2 = time.monotonic()

        # check for VOLUP key
        if  buttonVOLUP.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            display()
            Set_Volume()
            time.sleep(0.5)
            timer2 = time.monotonic()
                
        # check PREV key
        if buttonPREV.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            radio_stn -=2
            if radio_stn < 0:
               radio_stn = len(Radio_Stns) - 2
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            msg1 = (Radio_Stns[radio_stn])
            display()
            rs = Radio_Stns[radio_stn] + "               "[0:19]
            defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
            with open(config_file, 'w') as f:
                for item in defaults:
                    f.write("%s\n" % item)
            timer2 = time.monotonic()
            
        # check NEXT key
        if buttonNEXT.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            radio_stn +=2
            if radio_stn > len(Radio_Stns)- 2:
               radio_stn = 0
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            msg1 = (Radio_Stns[radio_stn])
            display()
            rs = Radio_Stns[radio_stn] + "               "[0:19]
            defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
            with open(config_file, 'w') as f:
                for item in defaults:
                    f.write("%s\n" % item)
            timer2 = time.monotonic()
            time.sleep(0.5)
            
        # check PLAY (STOP Radio) key
        if buttonPLAY.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            q.kill()
            radio = 0
            if len(tracks) > 0:
                msg1 = "Play.." + str(track_n)[0:5] + "   S"
            else:
                msg1 = "Radio Stopped      "
            display()
            defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
            with open(config_file, 'w') as f:
                for item in defaults:
                    f.write("%s\n" % item)
            time.sleep(2)
            

        # check for sleep_timer key
        if buttonSLEEP.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            timer1 = time.monotonic()
            msg1 = "Set SLEEP.. " + str(int(sleep_timer/60))
            msg2 = "HOLD for 20 to SHUTDOWN "
            msg3 = ""
            display()
            while buttonSLEEP.is_pressed:
                sleep_timer +=900
                if sleep_timer > 7200:
                     sleep_timer = 0
                sleep_timer_start = time.monotonic()
                msg1 = "Set SLEEP.. " + str(int(sleep_timer/60))
                display()
                time.sleep(1)
                if time.monotonic() - timer1 > 10:
                    msg2 = "SHUTDOWN in " + str(20-int(time.monotonic() - timer1))
                    display()
                if time.monotonic() - timer1 > 20:
                    # shutdown if pressed for 20 seconds
                    msg1 = "SHUTTING DOWN..."
                    msg2 = ""
                    msg3 = ""
                    msg4 = ""
                    display()
                    time.sleep(2)
                    msg1 = ""
                    display()
                    MP3_Play = 0
                    radio = 0
                    time.sleep(1)
                    os.system("sudo shutdown -h now")
            Disp_start = time.monotonic()
            time.sleep(0.5)
            msg1 = Radio_Stns[radio_stn]
            msg2 = ""
            display()
            timer2 = time.monotonic()
            xt = 2
                    
    # loop while playing MP3 tracks
    while MP3_Play == 1 :
        time.sleep(0.05)
        # check if clock synchronised
        if time.monotonic() - sync_timer > 60:
            sync_timer = time.monotonic()
            if os.path.exists ("/run/shm/sync.txt"):
                os.remove("/run/shm/sync.txt")
            os.system("timedatectl >> /run/shm/sync.txt")
            try:
                sync = []
                with open("/run/shm/sync.txt", "r") as file:
                    line = file.readline()
                    while line:
                        sync.append(line.strip())
                        line = file.readline()
                if sync[4] == "System clock synchronized: yes":
                    synced = 1
                else:
                    synced = 0
            except:
                pass
        # stop playing if end of album, in album mode
        cplayed +=1
        if cplayed > ctracks and album_mode == 1:
            status()
            msg1 = "Play.."
            ( msg2, msg3, msg4) = getSongDetails(Track_No)
            display()
            MP3_Play = 0
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_on = 1
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    msg2 = "SHUTDOWN in " + str(t)
                    msg3 = ""
                    msg4 = ""
                    display()
                else:
                    msg2 = "STOPPING in " + str(t)
                    msg3 = ""
                    msg4 = ""
                    display()
                if buttonSLEEP.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    msg1 = "SHUTTING DOWN..."
                else:
                    msg1 = "STOPPING........"
                time.sleep(0.05)
                msg2 = ""
                msg3 = ""
                msg4 = ""
                display()
                time.sleep(3)
                Disp_on = 0
                msg1 = ""
                display()
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid, SIGTERM)
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
                sleep_timer = 0
                stopped = 1
                MP3_Play = 0
            else:
                status()
                msg1 = "Play.." + str(track_n)[0:5] + txt
                display()
                time.sleep(0.05)
                Disp_start = time.monotonic()
            poll = p.poll()
            if poll == None:
                os.killpg(p.pid, SIGTERM)
                time.sleep(1)
                
        # try reloading tracks if none found
        if len(tracks) == 0 and stop == 0:
            reload()
            
        # try reloading tracks if one selected not found
        if len(tracks) > 0:
            track = getTrack(Track_No)
            if not os.path.exists (track) and stop == 0 :
                reload()
            
        # play selected track
        if MP3_Play == 1 and len(tracks) > 0:
          track = getTrack(Track_No)
          ( msg2, msg3, msg4) = getSongDetails(Track_No)
          if album_mode == 0:
              track_n = str(Track_No + 1) + "     "
          else:
              track_n = str(cplayed) + "/" + str(ctracks)
          if album_mode == 0:
              msg1 = "Track:" + str(track_n)[0:5] + "   0%"
          else:
              msg1 = "Track:" + str(track_n)[0:5] + "  " + str(played_pc)[-2:] + "%"
          rpistr = "mplayer " + " -quiet " +  '"' + track + '"'
          if Disp_on == 1:
              display()
          audio = MP3(track)
          track_len = audio.info.length
          p = subprocess.Popen(rpistr, shell=True, preexec_fn=os.setsid)
          poll = p.poll()
          while poll != None:
            poll = p.poll()
          timer2 = time.monotonic()
          timer1 = time.monotonic()
          xt = 0
          go = 1
          played = time.monotonic() - timer1
          
          # loop while playing selected MP3 track
          while poll == None and track_len - played > gap and (time.monotonic() - sleep_timer_start < sleep_timer or sleep_timer == 0):
            time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                
            # display clock (if enabled and synced)
            if show_clock == 1 and Disp_on == 0 and synced == 1:
                now = datetime.datetime.now()
                clock = now.strftime("%H:%M:%S")
                secs = now.strftime("%S")
                t = ""
                for r in range (0,random.randint(0,10)):
                    t += " "
                clock = t + clock
                time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                if sleep_timer > 0:
                    clock += " " + str(time_left)
                if secs != old_secs2 :
                  vp = random.randint(0,3)
                  msg1 = ""
                  msg2 = ""
                  msg3 = ""
                  msg4 = ""
                  if vp == 0:
                    msg1 = clock
                  elif vp == 1:
                    msg2 = clock
                  elif vp == 2:
                    msg3 = clock
                  elif vp == 3:
                    msg4 = clock
                  display()
                  old_secs2 = secs
                
            time.sleep(0.2)

            played  = time.monotonic() - timer1
            played_pc = int((played/track_len) *100)

            # DISPLAY OFF timer
            if time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1:
                msg1 = ""
                msg2 = ""
                msg3 = ""
                msg4 = ""
                Disp_on = 0
                display()
           
            # display titles, status etc
            if time.monotonic() - timer2 > 2 and Disp_on == 1:
                ( msg2, msg3, msg4) = getSongDetails(Track_No)
                timer2    = time.monotonic()
                played_pc =  "     " + str(played_pc)
                if album_mode == 0:
                    track_n = str(Track_No + 1) + "     "
                else:
                    track_n = str(cplayed) + "/" + str(ctracks) + "       "
                if xt < 2:
                    msg1 = "Track:" + str(track_n)[0:5] + "  " + str(played_pc)[-2:] + "%"
                elif xt == 2:
                    status()
                    msg1 = "Status...  " +  txt
                elif xt == 4 and sleep_timer != 0:
                    time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                    msg1 = "SLEEP: " + str(time_left) + " mins"
                elif xt == 5 and show_clock == 1 and synced == 1:
                    now = datetime.datetime.now()
                    clock = now.strftime("%H:%M:%S")
                    msg1 = clock
                elif xt == 3:
                    pmin = int(played/60)
                    psec = int(played - (pmin * 60))
                    psec2 = str(psec)
                    if psec < 10:
                        psec2 = "0" + psec2
                    lmin = int(track_len/60)
                    lsec = int(track_len - (lmin * 60))
                    lsec2 = str(lsec)
                    if lsec < 10:
                        lsec2 = "0" + lsec2
                    msg1 = " " + str(pmin) + ":" + str(psec2) + " of " + str(lmin) + ":" + str(lsec2)
                display()
                xt +=1
                if xt > 5:
                    xt = 0
                    
            # check for PLAY (STOP) key
            if  buttonPLAY.is_pressed:
                Disp_on = 1
                Disp_start = time.monotonic()
                timer1 = time.monotonic()
                os.killpg(p.pid, SIGTERM)
                msg1 = "Track Stopped"
                display()
                time.sleep(2)
                status()
                msg1 = "Play.." + str(track_n)[0:5] + txt
                msg2 = ""
                msg3 = ""
                msg4 = ""
                display()
                go = 0
                MP3_Play = 0
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                timer2 = time.monotonic()
                
            # check for PREVIOUS TRACK key 
            elif buttonPREV.is_pressed:
                Disp_on = 1
                Disp_start = time.monotonic()
                Disp_on = 1
                os.killpg(p.pid, SIGTERM)
                if go == 1:
                    Track_No -= 1
                    if Track_No < 0:
                        Track_No = len(tracks) + Track_No
                go = 0
                timer2 = time.monotonic()
                
            # check for NEXT TRACK key 
            elif  buttonNEXT.is_pressed:
                Disp_on = 1
                Disp_start = time.monotonic()
                os.killpg(p.pid, SIGTERM)
                if go == 1:
                    Track_No += 1
                    if Track_No > len(tracks) - 1:
                        Track_No = Track_No - len(tracks)
                go = 0
                timer2 = time.monotonic()

            # check for VOLDN  key
            elif buttonVOLDN.is_pressed:
              Disp_on = 1
              Disp_start = time.monotonic()
              display()
              time.sleep(0.5)
              timer1 = time.monotonic()
              timer  = time.monotonic()
              while buttonVOLDN.is_pressed and time.monotonic() - timer < 2:
                pass
              if time.monotonic() - timer < 1:
                if gapless == 0:
                    gap = gaptime
                    gapless = 1
                    msg2 = "Gapless ON"
                    msg3 = ""
                    msg4 = ""
                    display()
                    time.sleep(1)
                else:
                    gap = 0
                    gapless = 0
                    msg2 = "Gapless OFF"
                    msg3 = ""
                    msg4 = ""
                    display()
                    time.sleep(1)
                status()
                if album_mode == 0:
                    track_n = str(Track_No + 1) + "     "
                else:
                    track_n = "1/" + str(ctracks) + "       "
                msg1 = "Track.." + str(track_n)[0:5]
                display()
                defaults = [MP3_Play,radio,radio_stn,shuffled,album_mode,volume,gapless,Track_No]
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                time.sleep(0.5)
                timer2 = time.monotonic()
                xt = 2
              else:                  
                Set_Volume()
                timer2 = time.monotonic()

            # check for VOLUP key
            elif buttonVOLUP.is_pressed:
                Disp_on = 1
                Disp_start = time.monotonic()
                display()
                Set_Volume()
                time.sleep(0.5)
                timer2 = time.monotonic()
 
                           
            # check for SLEEP key
            elif  buttonSLEEP.is_pressed and Disp_on == 0:
                Disp_start = time.monotonic()
                Disp_on = 1
                status()
                msg1 = "Track.." + str(track_n)[0:5] + txt
                display()
                time.sleep(1)
                timer2 = time.monotonic()
            elif buttonSLEEP.is_pressed:
                Disp_on = 1
                timer1 = time.monotonic()
                if (sleep_timer == 0 and album_mode == 0) or (album_mode ==1 and sleep_timer == stimer + 60):
                    sleep_timer = 900
                elif sleep_timer == 0 and shuffled == 0 and album_mode == 1:
                    # determine album length to set sleep time
                    stimer = getRemainingAlbumTime(Track_No) 
                    sleep_timer = stimer + 60
                else:
                    sleep_timer = (time_left * 60) + 960
                    if sleep_timer > 10800:
                        sleep_timer = 0
                sleep_timer_start = time.monotonic()
                msg1 = "Set SLEEP.. " + str(int(sleep_timer/60))
                msg2 = "HOLD for 20 to SHUTDOWN "
                msg3 = ""
                msg4 = ""
                display()
                time.sleep(1)
                while buttonSLEEP.is_pressed:
                    if album_mode == 0:
                        sleep_timer +=900
                        if sleep_timer > 7200:
                            sleep_timer = 0
                        sleep_timer_start = time.monotonic()
                        msg1 = "Set SLEEP.. " + str(int(sleep_timer/60))
                        display()
                        time.sleep(1)
                    if time.monotonic() - timer1 > 10:
                        msg2 = "SHUTDOWN in " + str(20-int(time.monotonic() - timer1))
                    if time.monotonic() - timer1 > 20:
                        # shutdown if pressed for 20 seconds
                        msg1 = "SHUTTING DOWN..."
                        time.sleep(0.05)
                        msg2 = ""
                        msg3 = ""
                        msg4 = ""
                        display()
                        time.sleep(2)
                        msg1 = ""
                        display()
                        MP3_Play = 0
                        radio = 0
                        time.sleep(1)
                        os.system("sudo shutdown -h now")
                Disp_start = time.monotonic()
                timer2 = time.monotonic()
                xt = 2
                
            poll = p.poll()
            
          if go == 1:
            Track_No +=1
          if Track_No < 0:
            Track_No = len(tracks) + Track_No
          elif Track_No > len(tracks) - 1:
            Track_No = Track_No - len(tracks)
        





            
