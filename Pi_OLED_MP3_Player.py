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
import socket
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

import FnsPy

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

version  = "1.90"

# set default variables (saved in config_file and overridden at future startups)
VarsGlobal.radio_stn    = 0    # selected radio station at startup 
gapless      = 0    # set to 1 for gapless play
volume       = 50   # range 0 - 100
Track_No     = 0
player_mode  = 0    # 0 = Album, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
auto_start   = 0    # start playing radio or MP3 at startup
start_time   = 0    # poor man's pause : play resumes where last stopped

new_player_mode = 0


MP3_Play     = 0    # 1 when playing MP3s, else 0
radio        = 0    # 1 when playing radio, else 0


# variables set once
use_USB      = 0    # set to 0 if you ONLY use /home/pi/Music/... on SD card
usb_timer    = 6   # seconds to find USB present
sleep_timer  = 0    # sleep_timer timer in minutes, use 15,30,45,60 etc...set to 0 to disable
sleep_shutdn = 0    # set to 1 to shutdown Pi when sleep times out
Disp_timer   = 15   # Display timeout in seconds, set to 0 to disable
show_clock   = 0    # set to 1 to show clock, only use if on web or using RTC
gaptime      = 2    # set pre-start time for gapless, in seconds
myUsername   = "philip"   # os.getlogin() not always working when script run automatically
buttonHold   = 0.7    # number of seconds you need to hold keys to get different behaviour
numModes     = 4
activeTrack = Track_No # This holds the track num for which start_time applies
Disp_counter = 0
Disp_interval = 10   # how many loops between showing track info

playFavourites = False



baseDir = "/home/" + myUsername

Radio_Stns = ["Radio Paradise Rock","http://stream.radioparadise.com/rock-192",
              "Radio Paradise Main","http://stream.radioparadise.com/mp3-320",
              "Radio Paradise Mellow","http://stream.radioparadise.com/mellow-192",
              "Radio Caroline","http://sc6.radiocaroline.net:10558/"]

playerModeNames = ( "Album", "Album Rand", "Rand Tracks", "Radio" )

debugOut = True


# GPIO BUTTONS GPIO BCM numbers (Physical pin numbers)
#############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
PLAY   = 12 # (32) STOP                        | PLAY (MP3 / RADIO)   START PLAY FAVS 
NEXT   = 7  # (26) NEXT TRACK/RADIO - NEXT ALB | BROWSE NEXT ALB - BROWSE NEXT ARTIST
PREV   = 20 # (38) PREV TRACK/RADIO - PREV ALB | BROWSE PREV ALB - BROWSE PREV ARTIST
VOLDN  = 16 # (36) VOL DN                      | VOL DN
VOLUP  = 8  # (24) VOL UP                      | VOL UP
FAVMODE = 25# (22) CURRENT ALB > FAV ADD - REM | ROTATE MODE Album  Album Rand  Rand Tracks  Radio - HOLD10s = SHUTDOWN

favourites_file = baseDir + "/favourites.txt"


albumFavourites = []
# read favourites if existing
if os.path.exists(favourites_file):
    with open(favourites_file, "r") as file:
       line = file.readline()
       while line:
          albumFavourites.append(line.strip())
          line = file.readline()
    albumFavourites = list(map(int,albumFavourites))
    debugMsg("Loading Favourites from file.")
    debugMsg(albumFavourites)






# check config file exists, if not then write default values
config_file = baseDir + "/OLEDconfig.txt"
if not os.path.exists(config_file):
    FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])

# read config file : radio_stn, gapless, volume, Track_No, player_mode, auto_start
config = []
with open(config_file, "r") as file:
   line = file.readline()
   while line:
      config.append(line.strip())
      line = file.readline()
config = list(map(int,config))
debugMsg("Loading config from file.")
debugMsg(config)

radio_stn  = config[0]
gapless    = config[1]
volume     = config[2]
Track_No   = config[3]
player_mode = config[4] # 0 = Album, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
auto_start = config[5]
start_time = config[6]

activeTrack = Track_No

if auto_start:
    if player_mode == 3:  # radio
        MP3_Play   = 0
        radio = 1
    else:
        MP3_Play   = 1
        radio = 0

trackHistory = []


if Track_No < 0:
    Track_No = 0



# read radio_stns.txt - format: Station Name,Station URL
if os.path.exists (baseDir + "/radio_stns.txt"): 
    with open(baseDir + "/radio_stns.txt","r") as textobj:
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
buttonFAVMODE = Button(FAVMODE)

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
remainTracks     = 0
currentTrack     = 0
stopped     = 0
played_pc   = 0
synced      = 0
reloading   = 0
abort_sd    = 1
usb_found   = 0



# find username
h_user  = []
h_user.append(myUsername)   # os.getlogin() not always working when script run automatically

favouritesIndex = 0





FnsPy.outputToDisplay("MP3 Player: v" + version, "", "", "")
time.sleep(2)
stop = 0








# read previous usb free space of upto 4 usb devices, to see if usb data has changed
if not os.path.exists(baseDir + "/freedisk.txt"):
    with open(baseDir + "/freedisk.txt", "w") as f:
        for item in freedisk:
            f.write("%s\n" % item)
freedisk = []            
with open(baseDir + "/freedisk.txt", "r") as file:
    line = file.readline()
    while line:
         freedisk.append(line.strip())
         line = file.readline()
         
# check if SD Card ~/Music has changed
if not os.path.exists(baseDir + "/freeSD.txt"):
    with open(baseDir + "/freeSD.txt", "w") as f:
            f.write("0")
with open(baseDir + "/freeSD.txt", "r") as file:
    line = file.readline()



total_size = get_dir_size("/home/" +  h_user[0] + "/Music")
if line != str(total_size):
    with open(baseDir + "/freeSD.txt", "w") as f:
        f.write(str(total_size))
    reloading = 1

# load MP3 tracks

if not os.path.exists(baseDir + "/tracks.txt") and stop == 0:
    Track_No = FnsPy.reload(stop)
else:
    with open(baseDir + "/tracks.txt", "r") as file:
        line = file.readline()
        while line:
             VarsGlobal.tracks.append(line.strip())
             line = file.readline()

FnsPy.outputToDisplay("Tracks: " + str(FnsPy.getNumTracks()), "", "", "")


# check if USB mounted and find USB storage
if use_USB == 1:
    start = time.monotonic()
    FnsPy.outputToDisplay("Checking for USB", "", "", "")
    while time.monotonic() - start < usb_timer:
        usb = glob.glob("/media/" +  h_user[0] + "/*")
        usb_found = len(usb)
        FnsPy.outputToDisplay("Checking for USB", "Found: " + str(usb_found) + " USBs", str(int(usb_timer -(time.monotonic() - start))), "")
        time.sleep(1)
    FnsPy.outputToDisplay("Checking for USB", "", "", "")
    if usb_found > 0:
        # check if usb contents have changed, if so then reload tracks
        free = ["0","0","0","0"]
        for xy in range(0,len(usb)):
            st3 = os.statvfs(usb[xy])
            free[xy] = str((st3.f_bavail * st3.f_frsize)/1100000)
        for xy in range(0,3):
            if str(free[xy]) != freedisk[xy]:
                with open(baseDir + "/freedisk.txt", "w") as f:
                    for item in free:
                        f.write("%s\n" % item)
                reloading = 1
    else:
        freedisk = ["0","0","0","0"]
        with open(baseDir + "/freedisk.txt", "w") as f:
            for item in freedisk:
                f.write("%s\n" % item)
        FnsPy.outputToDisplay("Checking for USB", "No USB Found !!", "", "")
        sd_tracks = glob.glob("/home/" + h_user[0] + "/Music/*/*/*.mp3")
        time.sleep(2)
        if len(sd_tracks) != FnsPy.getNumTracks():
            reloading = 1
        FnsPy.outputToDisplay("Checking for USB", "", "", "")

if reloading == 1 and stop == 0:
    Track_No = FnsPy.reload(stop)



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
    
# try reloading tracks if one selected not found
if FnsPy.getNumTracks() > 0:
    track = FnsPy.getTrack(Track_No)
    if not os.path.exists (track) and usb_found > 0 and stop == 0:
        Track_No = FnsPy.reload(stop)

# populate albumDictionary, artistDictionary, albumList, artistList
loadTrackDictionaries()

# wait for internet connection
if radio == 1:
    FnsPy.outputToDisplay("Waiting for Radio...", "", "", "")
    time.sleep(10)
    q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] ,shell=False)
    FnsPy.outputToDisplay((Radio_Stns[radio_stn]), "", "", "")
    
else:
    (remainTracks, currentTrack) = getAlbumTracksInfo(Track_No)
    stimer = getRemainingAlbumTime(Track_No)    





showTrackProgress(Track_No, "STOP", -1)

if gapless == 0:
    gap = 0
else:
    gap = gaptime    
    


if FnsPy.getNumTracks() > 0:
    ( artist, album, song ) = getArtistAlbumSongNames(Track_No)

sleep_timer_start = time.monotonic()
Disp_start        = time.monotonic()
timer1            = time.monotonic()
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

#Track_No = selectNextTrack(Track_No)

buttonFAVMODE_action = ""
buttonPREV_action = ""
buttonNEXT_action = ""
buttonPLAY_action = ""

chooseModeActive = False
browseActive = False
browseMode = "Track"

while True:    
    #################################################
    ######       loop while stopped   ###############
    #################################################
    #debugMsg("MP3 Play: " + str(MP3_Play) + "   radio: " + str(radio))
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
            
        # display Track
        if (time.monotonic() - timer1 > 3 and Disp_on == 1 and FnsPy.getNumTracks() > 0) and not (chooseModeActive or browseActive):
            timer1 = time.monotonic()
            showTrackProgress(Track_No, "STOP", -1) 


        # display clock (if enabled and synced)
        if (show_clock == 1 and Disp_on == 0 and synced == 1 and stopped == 0 and abort_sd == 1) and not (chooseModeActive or browseActive):
            now = datetime.datetime.now()
            clock = now.strftime("%H:%M:%S")
            secs = now.strftime("%S")
            t = ""
            for r in range (0,random.randint(0,10)):
                t += " "
            clock = t + clock
            if secs != old_secs2 :
                FnsPy.outputToDisplayRand(clock)
                old_secs2 = secs

        # DISPLAY OFF timer
        if (time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1) and not (chooseModeActive or browseActive):
            FnsPy.outputToDisplay("", "", "", "")
            Disp_on = 0

            
        # sleep_timer timer
        if (time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0) and not (chooseModeActive or browseActive):
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    FnsPy.outputToDisplay("", "SHUTDOWN in " + str(t), "", "")
                else:
                    FnsPy.outputToDisplay("", "STOPPING in " + str(t), "", "")
                if buttonFAVMODE.is_pressed or buttonPLAY.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    FnsPy.outputToDisplay("SHUTTING DOWN...", "", "", "")
                else:
                    FnsPy.outputToDisplay("STOPPING........", "", "", "")
                time.sleep(3)
                FnsPy.outputToDisplay("", "", "", "")
                sleep_timer = 0 
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
            else:
                showTrackProgress(Track_No, "STOP", -1)
            Disp_start = time.monotonic()




        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # PLAY               STOP                        | PLAY (MP3 / RADIO)   START PLAY FAVS 
        ######################################################################################

            




        # check for PLAY key when stopped
        if buttonPLAY_action:
            if not buttonPLAY.is_pressed:   # actions when button released
                debugMsg("buttonPLAY: " + buttonPLAY_action)
                if buttonPLAY_action == "PUSH":   # released after push
                    # player mode is radio
                    if player_mode == 3:
                        q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
                        time.sleep(0.05)
                        FnsPy.outputToDisplay(Radio_Stns[radio_stn], "", "", "")
                        rs = Radio_Stns[radio_stn]
                        while buttonPLAY.is_pressed:
                            pass
                        time.sleep(1)
                        radio    = 1
                        MP3_Play = 0
                        FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])                
                    # player mode is not radio
                    else:
                        if player_mode == 0 or player_mode == 1:
                            (remainTracks, currentTrack) = getAlbumTracksInfo(Track_No)
                            stimer = getRemainingAlbumTime(Track_No) 
                        MP3_Play = 1
                        radio    = 0
                        FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])     
                elif buttonPLAY_action == "HOLD":   # released after hold
                    # player mode is not radio and rand tracks
                    # 0 = Album, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
                    debugMsg("buttonPLAY: released after HOLD")
                    if player_mode == 0 or player_mode == 1:    # start playing favourites
                        debugMsg("Choose first favourite album.")
                        FnsPy.outputToDisplayFlashing("", "START ALBUM FAVS" , "", "")
                        Track_No = goToNextFavourite()   # play from start of next favourite
                        (remainTracks, currentTrack) = getAlbumTracksInfo(Track_No)
                        stimer = getRemainingAlbumTime(Track_No) 
                        MP3_Play = 1
                        radio    = 0
                        playFavourites = True
                        FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])                         
                buttonPLAY_action = ""
            else:   # actions when button held               
                if (time.monotonic() - buttonPLAY_timer) > buttonHold:
                    buttonPLAY_action = "HOLD"
        else:                
            if buttonPLAY.is_pressed:   # actions when button held
                buttonPLAY_action = "PUSH"
                buttonPLAY_timer = time.monotonic()
                if (time.monotonic() - buttonPLAY_timer) > buttonHold:
                    buttonPLAY_action = "HOLD"





        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # NEXT              NEXT TRACK/RADIO - NEXT ALB | BROWSE NEXT ALB - BROWSE NEXT ARTIST 
        ######################################################################################
                


        # check NEXT key when stopped
        if buttonNEXT_action:
            if not buttonNEXT.is_pressed:   # actions when button released
                debugMsg("buttonNEXT: " + buttonNEXT_action)
                # button released after push - action new selection - show track list
                Track_No = browseMusic(Track_No, browseMode, 1)
                buttonNEXT_action = ""
                browseActive = True
                Disp_timer = 35     # keep display on longer while browsing
                playFavourites = False
                browseTimer = time.monotonic()
            else:   # actions when button held
                buttonNEXT_action = "HOLD"
                buttonNEXT_holdtime = time.monotonic() - buttonNEXT_timer 
                if buttonNEXT_holdtime > (buttonHold + 2) and browseMode == "Track":  # after holding 2 seconds start browsing albums
                    browseMode = "Album"
                if buttonNEXT_holdtime > (buttonHold + 4) and browseMode == "Album":  # after holding 4 seconds start browsing artists
                    browseMode = "Artist"
                if int((buttonNEXT_holdtime / 0.3)) % 2:
                    Track_No = browseMusic(Track_No, browseMode, 1)
                    browseActive = True
                    Disp_timer = 35     # keep display on longer while browsing
                    playFavourites = False
                    browseTimer = time.monotonic()
        else:                
            if buttonNEXT.is_pressed:   # actions when button held
                buttonNEXT_action = "PUSH"
                buttonNEXT_timer = time.monotonic()
                if (time.monotonic() - buttonNEXT_timer) > buttonHold:
                    buttonNEXT_action = "HOLD"

        if browseActive and (time.monotonic() - browseTimer) > 3:
            if browseMode == "Artist":
                browseMode = "Album"
                browseTimer = time.monotonic()
            elif browseMode == "Album":
                browseMode = "Track"
                browseTimer = time.monotonic()
            elif browseMode == "Track":              
                browseActive = False

        if Disp_timer != 15 and not browseActive:
            Disp_timer = 15     # revert display timout length


        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # PREV              PREV TRACK/RADIO - PREV ALB | BROWSE PREV ALB - BROWSE PREV ARTIST 
        ######################################################################################

        # check NEXT key when stopped
        if buttonPREV_action:
            if not buttonPREV.is_pressed:   # actions when button released
                debugMsg("buttonPREV: " + buttonPREV_action)
                # button released after push - action new selection - show track list
                Track_No = browseMusic(Track_No, browseMode, -1)
                buttonPREV_action = ""
                browseActive = True
                Disp_timer = 35     # keep display on longer while browsing
                playFavourites = False
                browseTimer = time.monotonic()
            else:   # actions when button held
                buttonPREV_action = "HOLD"
                buttonPREV_holdtime = time.monotonic() - buttonPREV_timer 
                if buttonPREV_holdtime > (buttonHold + 3) and browseMode == "Track":  # after holding 3 seconds start browsing albums
                    browseMode = "Album"
                if buttonPREV_holdtime > (buttonHold + 8) and browseMode == "Album":  # after holding 8 seconds start browsing artists
                    browseMode = "Artist"
                if int((buttonPREV_holdtime / 0.3)) % 2:
                    Track_No = browseMusic(Track_No, browseMode, -1)
                    browseActive = True
                    Disp_timer = 35     # keep display on longer while browsing
                    playFavourites = False
                    browseTimer = time.monotonic()
        else:                
            if buttonPREV.is_pressed:   # actions when button held
                buttonPREV_action = "PUSH"
                buttonPREV_timer = time.monotonic()
                if (time.monotonic() - buttonPREV_timer) > buttonHold:
                    buttonPREV_action = "HOLD"





        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # VOLDN             VOL DN                      | VOL DN
        # VOLUP             VOL UP                      | VOL UP 
        ######################################################################################


        # check for VOLUP or VOLDN key when stopped
        if buttonVOLUP.is_pressed and buttonVOLDN.is_pressed:
            debugMsg("button VOLUP and VOLDN PUSHED at same time")
            ipAddrLine = "" 
            ipAddr = get_ip()
            if ipAddr:
                ipAddrLine = "IP: " + str(ipAddr)
            FnsPy.outputToDisplay("", "PLAY = SHUTDOWN" , "PREV = BACK", ipAddrLine)
            decisionMade = False
            loopsRemaining = 50
            while loopsRemaining and not decisionMade:
                if buttonPLAY.is_pressed:
                    FnsPy.outputToDisplayFlashing("SHUTTING DOWN...", "", "", "")
                    time.sleep(2)
                    FnsPy.outputToDisplay("", "", "", "")
                    MP3_Play = 0
                    radio = 0
                    time.sleep(1)
                    os.system("sudo shutdown -h now")
                if buttonPREV.is_pressed:
                    decisionMade = True
                loopsRemaining -= 1
                time.sleep(0.1)
        elif buttonVOLUP.is_pressed or buttonVOLDN.is_pressed:
            debugMsg("button VOLUP/VOLDN PUSHED/HELD")
            if Disp_on == 0:
                Disp_on = 1
                Disp_start = time.monotonic()
                showTrackProgress(Track_No, "STOP", -1)
                time.sleep(0.5)
            Set_Volume()
            time.sleep(0.5)





                
        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # FAVMODE           CURRENT ALB > FAV ADD - REM | ROTATE MODE Album  Album Rand  Rand Tracks  Radio - HOLD10s = SHUTDOWN
        ######################################################################################

        # check for FAVMODE key when stopped
        if buttonFAVMODE_action:
            if not buttonFAVMODE.is_pressed:   # actions when button released
                debugMsg("buttonFAVMODE: " + buttonFAVMODE_action)
                if buttonFAVMODE_action == "PUSH":
                    # display current mode
                    FnsPy.outputToDisplay("CURRENT MODE:", playerModeNames[player_mode] + "   " , "", "")
                    time.sleep(1)
                elif buttonFAVMODE_action == "HOLD":
                    if player_mode != new_player_mode:
                        player_mode = new_player_mode
                        FnsPy.outputToDisplayFlashing("", playerModeNames[player_mode] + "   " , "", "")
                        time.sleep(1)
                        if player_mode == 0:   # Album
                            radio = 0
                            MP3_play = 1
                            Track_No = selectNextTrack(Track_No)
                            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
                        elif player_mode == 1:   # Album Rand
                            radio = 0
                            MP3_play = 1                   
                            Track_No = selectNextTrack(Track_No)
                            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
                        elif player_mode == 2:   # Rand Tracks
                            radio = 0
                            MP3_play = 1                  
                            Track_No = selectNextTrack(Track_No)
                            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
                        else:     # Radio
                            radio = 1
                            MP3_play = 0
                            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn]] , shell=False)
                            FnsPy.outputToDisplay(Radio_Stns[radio_stn], "", "", "")
                            rs = Radio_Stns[radio_stn] + "               "[0:19]
                            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
                buttonFAVMODE_action = ""
                chooseModeActive = False
            else:   # actions when button held               
                new_player_mode = (int(time.monotonic() - buttonFAVMODE_timer - buttonHold) % numModes ) # this will change each second as button held
                FnsPy.outputToDisplay("CURRENT MODE:", playerModeNames[new_player_mode] + "   " , "", "")
                buttonFAVMODE_action = "HOLD"
                chooseModeActive = True
        else:                
            if buttonFAVMODE.is_pressed:   # actions when button held
                buttonFAVMODE_action = "PUSH"
                buttonFAVMODE_timer = time.monotonic()
                #while buttonFAVMODE.is_pressed and (time.monotonic() - buttonFAVMODE_timer) < buttonHold:
                #    pass
                if (time.monotonic() - buttonFAVMODE_timer) > buttonHold:
                    buttonFAVMODE_action = "HOLD"
                    #orig_player_mode = player_mode

                
                  



            

            
    #######################################################
    ######       loop while playing radio   ###############
    #######################################################
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
            FnsPy.outputToDisplay("", "", "", "")
            Disp_on = 0

            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            Disp_on = 1
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    FnsPy.outputToDisplay("", "SHUTDOWN in " + str(t), "", "")
                else:
                    FnsPy.outputToDisplay("", "STOPPING in " + str(t), "", "")
                if buttonFAVMODE.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    FnsPy.outputToDisplay("SHUTTING DOWN...", "", "", "")
                else:
                    FnsPy.outputToDisplay("STOPPING........", "", "", "")
                time.sleep(1)
                FnsPy.outputToDisplay("", "", "", "")
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
        if sleep_timer > 0:
            shutdownMsg = "Shutdown: " + str(time_left) + "mins"
        else:
            shutdownMsg = ""
        if Disp_on == 1:
            if show_clock == 1 and synced == 1:
                FnsPy.outputToDisplay("", "      " + clock, shutdownMsg, "")
            else:
                FnsPy.outputToDisplay("", "", shutdownMsg, "")
        t = ""
        for r in range (0,random.randint(0,10)):
            t += " "
        clock = t + clock
        if show_clock == 1 and Disp_on == 0 and synced == 1:
            if secs != old_secs:
                if sleep_timer > 0:
                    clock = clock + " " + str(time_left)
                FnsPy.outputToDisplayRand(clock)
                old_secs = secs
            
         # check for VOLDN  key
        if  buttonVOLDN.is_pressed :
            debugMsg("buttonVOLDN PUSH")
            Disp_on = 1
            Disp_start = time.monotonic()
            FnsPy.outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            Set_Volume()
            time.sleep(0.5)


        # check for VOLUP key
        if  buttonVOLUP.is_pressed:
            debugMsg("buttonVOLUP PUSH")
            Disp_on = 1
            Disp_start = time.monotonic()
            FnsPy.outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            Set_Volume()
            time.sleep(0.5)

                
        # check PREV key
        if buttonPREV.is_pressed:
            debugMsg("buttonPREV PUSH")
            Disp_on = 1
            Disp_start = time.monotonic()
            radio_stn -=2
            if radio_stn < 0:
               radio_stn = len(Radio_Stns) - 2
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            FnsPy.outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            rs = Radio_Stns[radio_stn] + "               "[0:19]
            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])

            
        # check NEXT key
        if buttonNEXT.is_pressed:
            debugMsg("buttonNEXT PUSH")
            Disp_on = 1
            Disp_start = time.monotonic()
            radio_stn +=2
            if radio_stn > len(Radio_Stns)- 2:
               radio_stn = 0
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            FnsPy.outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            rs = Radio_Stns[radio_stn] + "               "[0:19]
            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
            time.sleep(0.5)
            
        # check PLAY (STOP Radio) key
        if buttonPLAY.is_pressed:
            debugMsg("buttonPLAY PUSH")
            Disp_on = 1
            Disp_start = time.monotonic()
            q.kill()
            radio = 0
            FnsPy.outputToDisplay("Radio Stopped      ", "", "", "")
            FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
            time.sleep(2)
            


                    
    ############################################################
    ######       loop while playing MP3 tracks   ###############
    ############################################################
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
        #(remainTracks, currentTrack) = getAlbumTracksInfo(Track_No)

        #if currentTrack > remainTracks and player_mode != 2:
        #   MP3_Play = 0
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_on = 1
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    FnsPy.outputToDisplay("", "SHUTDOWN in " + str(t), "", "")
                else:
                    FnsPy.outputToDisplay("", "STOPPING in " + str(t), "", "")
                if buttonFAVMODE.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    FnsPy.outputToDisplay("SHUTTING DOWN...", "", "", "")
                else:
                    FnsPy.outputToDisplay("STOPPING........", "", "", "")
                time.sleep(0.05)
                time.sleep(3)
                Disp_on = 0
                FnsPy.outputToDisplay("", "", "", "")
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid, SIGTERM)
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
                sleep_timer = 0
                stopped = 1
                MP3_Play = 0
            else:
                FnsPy.outputToDisplay("Play.." + str(track_n)[0:5] + playerStatus(player_mode), "", "", "")
                time.sleep(0.05)
                Disp_start = time.monotonic()
            poll = p.poll()
            if poll == None:
                os.killpg(p.pid, SIGTERM)
                time.sleep(1)
                
        # try reloading tracks if none found
        if FnsPy.getNumTracks() == 0 and stop == 0:
            Track_No = FnsPy.reload(stop)
            
        # try reloading tracks if one selected not found
        if FnsPy.getNumTracks() > 0:
            track = FnsPy.getTrack(Track_No)
            if not os.path.exists (track) and stop == 0 :
                Track_No = FnsPy.reload(stop)


            
        # play selected track
        if MP3_Play == 1 and FnsPy.getNumTracks() > 0:
            p = playMP3(Track_No)
            startPlayTimer = time.monotonic()
            Disp_on = 1
            Disp_start = time.monotonic()
            showTrackProgressEDIT(Track_No, "PLAY", startPlayTimer)
            poll = p.poll()
            while poll != None:
              poll = p.poll()
            goToNextTrack = 1
            # loop while playing selected MP3 track
            remainingTrackTime = getRemainingTime(Track_No, startPlayTimer)
            while poll == None and remainingTrackTime > gap and (time.monotonic() - sleep_timer_start < sleep_timer or sleep_timer == 0):
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
                        FnsPy.outputToDisplayRand(clock)
                        old_secs2 = secs
                  
                time.sleep(0.2)
  
  
                # DISPLAY OFF timer
                if time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1:
                    FnsPy.outputToDisplay("", "", "", "")
                    Disp_on = 0
                

                if Disp_on:
                    if (Disp_counter  % Disp_interval) == 0:
                        showTrackProgressEDIT(Track_No, "PLAY", startPlayTimer)
                        Disp_counter = 0
                    Disp_counter += 1

             
                # display track progress etc
                #if played > 2 and Disp_on == 1:
                #    (played, played_pc, track_len) = getPlayDuration(Track_No, startPlayTimer)
                #    showTrackProgress(Track_No, "PLAY", played_pc)

  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # PLAY               STOP                        | PLAY (MP3 / RADIO)   START PLAY FAVS 
                ######################################################################################
                      
                # check for PLAY (STOP) key when playing MP3
                if buttonPLAY.is_pressed:
                    debugMsg("buttonPLAY PUSH")
                    Disp_on = 1
                    Disp_start = time.monotonic()
                    start_time = start_time + getPlayedTime(Track_No, startPlayTimer)
                    if start_time > 5:
                        start_time -= 5
                    os.killpg(p.pid, SIGTERM)
                    FnsPy.outputToDisplay("Track Stopped", "", "", "")
                    time.sleep(2)
                    showTrackProgress(Track_No, "STOP", -1)
                    goToNextTrack = 0
                    MP3_Play = 0
                    FnsPlayer.writeDefaults([radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time])
  
  
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # NEXT              NEXT TRACK/RADIO - NEXT ALB | BROWSE NEXT ALB - BROWSE NEXT ARTIST 
                ######################################################################################
  
                  

  

                # check for NEXT key when playing MP3
                if buttonNEXT_action:
                    if not buttonNEXT.is_pressed:   # perform actions when button released
                        debugMsg("buttonNEXT: " + buttonNEXT_action)
                        Disp_start = time.monotonic()
                        Disp_on = 1
                        os.killpg(p.pid, SIGTERM)                        
                        if buttonNEXT_action == "PUSH":
                            # push action
                            FnsPy.outputToDisplayFlashing("", "> NEXT TRACK", "", "")
                            Track_No = selectNextTrack(Track_No)
                        elif buttonNEXT_action == "HOLD":
                            # hold action
                            if player_mode == 0:   # Album
                                if playFavourites:
                                    FnsPy.outputToDisplayFlashing("", "> NEXT FAV ALBUM", "", "")
                                    Track_No = goToNextFavourite()
                                else:
                                    FnsPy.outputToDisplayFlashing("", "> NEXT ALBUM", "", "")
                                    Track_No = goToNextAlbum(Track_No)
                            elif player_mode == 1:   # Album Rand
                                if playFavourites:
                                    FnsPy.outputToDisplayFlashing("", "> NEXT FAV ALBUM", "", "")
                                    Track_No = goToNextFavourite()
                                else:
                                    FnsPy.outputToDisplayFlashing("", "> RAND ALBUM", "", "")
                                    Track_No = goToRandomAlbum()
                            else:
                                FnsPy.outputToDisplayFlashing("", "> NEXT TRACK", "", "")
                                Track_No = selectNextTrack(Track_No)
                        showTrackProgress(Track_No, "PLAY", -1)
                        goToNextTrack = 0
                        buttonNEXT_action = ""
                else:                
                    if buttonNEXT.is_pressed:    # perform actions when button held
                        buttonNEXT_action = "PUSH"
                        buttonNEXT_timer = time.monotonic()
                        #debugMsg("Interval 1: " + str(time.monotonic() - buttonNEXT_timer))
                        while buttonNEXT.is_pressed and (time.monotonic() - buttonNEXT_timer) < buttonHold:
                            pass
                        #debugMsg("Interval 2: " + str(time.monotonic() - buttonNEXT_timer))
                        if (time.monotonic() - buttonNEXT_timer) > buttonHold:
                            buttonNEXT_action = "HOLD"    
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # PREV              PREV TRACK/RADIO - PREV ALB | BROWSE PREV ALB - BROWSE PREV ARTIST 
                ######################################################################################
                  




                # check for PREV key when playing MP3
                if buttonPREV_action:
                    if not buttonPREV.is_pressed:
                        debugMsg("buttonPREV: " + buttonPREV_action)
                        Disp_start = time.monotonic()
                        Disp_on = 1
                        os.killpg(p.pid, SIGTERM)                        
                        if buttonPREV_action == "PUSH":
                            # push action
                            FnsPy.outputToDisplayFlashing("", "> PREV TRACK", "", "")
                            Track_No = selectPrevTrack(Track_No)
                        elif buttonPREV_action == "HOLD":  # hold action
                            if player_mode == 0:   # Album
                                if playFavourites:
                                    FnsPy.outputToDisplayFlashing("", "> PREV FAV ALBUM", "", "")
                                    Track_No = goToPrevFavourite()
                                else:
                                    FnsPy.outputToDisplayFlashing("", "> PREV ALBUM", "", "")
                                    Track_No = goToPrevAlbum(Track_No)                                    
                            elif player_mode == 1:   # Album Rand
                                if playFavourites:
                                    FnsPy.outputToDisplayFlashing("", "> PREV FAV ALBUM", "", "")
                                    Track_No = goToPrevFavourite()
                                else:
                                    FnsPy.outputToDisplayFlashing("", "> RAND ALBUM", "", "")
                                    Track_No = goToRandomAlbum()
                            else:                            
                                FnsPy.outputToDisplayFlashing("", "> PREV TRACK", "", "")
                                Track_No = selectPrevTrack(Track_No)
                        showTrackProgress(Track_No, "PLAY", -1)
                        goToNextTrack = 0
                        buttonPREV_action = ""
                else:                
                    if buttonPREV.is_pressed:
                        buttonPREV_action = "PUSH"
                        buttonPREV_timer = time.monotonic()
                        #debugMsg("Interval 1: " + str(time.monotonic() - buttonPREV_timer))
                        while buttonPREV.is_pressed and (time.monotonic() - buttonPREV_timer) < buttonHold:
                            pass
                        #debugMsg("Interval 2: " + str(time.monotonic() - buttonPREV_timer))
                        if (time.monotonic() - buttonPREV_timer) > buttonHold:
                            buttonPREV_action = "HOLD"  
  
  
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # VOLDN             VOL DN                      | VOL DN
                # VOLUP             VOL UP                      | VOL UP 
                ######################################################################################
  
  
                # check for VOLDN or VOLDN key when playing MP3
                if buttonVOLUP.is_pressed or buttonVOLDN.is_pressed:
                    debugMsg("buttonVOLUP/VOLDN PUSH/HELD")
                    if Disp_on == 0:
                        Disp_on = 1
                        Disp_start = time.monotonic()
                        showTrackProgress(Track_No, "PLAY", played_pc)
                        time.sleep(0.5)
                    Set_Volume()
                    time.sleep(0.5)
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # FAVMODE   CURRENT ALB > FAV ADD/REM  -        | ROTATE MODE Album  Album Rand  Rand Tracks  Radio - HOLD10s = SHUTDOWN
                ######################################################################################
                             
                # check for FAVMODE key when playing MP3
                if buttonFAVMODE_action:
                    if not buttonFAVMODE.is_pressed:
                        debugMsg("buttonFAVMODE: " + buttonFAVMODE_action)
                        if buttonFAVMODE_action == "PUSH":
                            # add current album to favourites
                            Disp_on = 1
                            Disp_start = time.monotonic()
                            add_removeCurrentAlbumFavs(Track_No)
                        buttonFAVMODE_action = ""
                else:                
                    if buttonFAVMODE.is_pressed:
                        buttonFAVMODE_action = "PUSH"
                        buttonFAVMODE_timer = time.monotonic()
                        #debugMsg("Interval 1: " + str(time.monotonic() - buttonFAVMODE_timer))
                        while buttonFAVMODE.is_pressed and (time.monotonic() - buttonFAVMODE_timer) < buttonHold:
                            pass
                        #debugMsg("Interval 2: " + str(time.monotonic() - buttonFAVMODE_timer))
                        if (time.monotonic() - buttonFAVMODE_timer) > buttonHold:
                            buttonFAVMODE_action = "HOLD"
                      
                


  
                  
                poll = p.poll()
            
            if goToNextTrack == 1:
                Disp_on = 1
                Disp_start = time.monotonic()
                Track_No = selectNextTrack(Track_No)

        





            
