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

version  = "1.90"

# set default variables (saved in config_file and overridden at future startups)
radio_stn    = 0    # selected radio station at startup 
gapless      = 0    # set to 1 for gapless play
volume       = 50   # range 0 - 100
Track_No     = 0
player_mode  = 0    # 0 = Album Favs, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
auto_start   = 0    # start playing radio or MP3 at startup



MP3_Play     = 0    # 1 when playing MP3s, else 0
radio        = 0    # 1 when playing radio, else 0


# variables set once
use_USB      = 0    # set to 0 if you ONLY use /home/pi/Music/... on SD card
usb_timer    = 6   # seconds to find USB present
sleep_timer  = 0    # sleep_timer timer in minutes, use 15,30,45,60 etc...set to 0 to disable
sleep_shutdn = 0    # set to 1 to shutdown Pi when sleep times out
Disp_timer   = 60   # Display timeout in seconds, set to 0 to disable
show_clock   = 0    # set to 1 to show clock, only use if on web or using RTC
gaptime      = 2    # set pre-start time for gapless, in seconds
myUsername   = "philip"   # os.getlogin() not always working when script run automatically
buttonHold   = 3    # number of seconds you need to hold keys to get different behaviour
numModes     = 4

Radio_Stns = ["Radio Paradise Rock","http://stream.radioparadise.com/rock-192",
              "Radio Paradise Main","http://stream.radioparadise.com/mp3-320",
              "Radio Paradise Mellow","http://stream.radioparadise.com/mellow-192",
              "Radio Caroline","http://sc6.radiocaroline.net:10558/"]

playerModeNames = ( "Album Favs", "Album Rand", "Rand Tracks", "Radio" )


# GPIO BUTTONS GPIO BCM numbers (Physical pin numbers)
#############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
PLAY   = 12 # (32) STOP                        | PLAY (MP3 / RADIO)   START PLAY FAVS 
NEXT   = 7  # (26) NEXT TRACK/RADIO - NEXT ALB | BROWSE NEXT ALB - BROWSE NEXT ARTIST
PREV   = 20 # (38) PREV TRACK/RADIO - PREV ALB | BROWSE PREV ALB - BROWSE PREV ARTIST
VOLDN  = 16 # (36) VOL DN                      | VOL DN
VOLUP  = 8  # (24) VOL UP                      | VOL UP
FAVMODE = 25# (22) CURRENT ALB > FAV ADD - REM | ROTATE MODE Album Favs  Album Rand  Rand Tracks  Radio - HOLD10s = SHUTDOWN

favourites_file = "favourites.txt"

def writeFavourites():
    global favourites_file, albumFavourites
    with open(favourites_file, 'w') as f:
        for item in albumFavourites:
            f.write("%s\n" % item)

albumFavourites = []
# read favourites if existing
if os.path.exists(favourites_file):
    with open(favourites_file, "r") as file:
       line = file.readline()
       while line:
          albumFavourites.append(line.strip())
          line = file.readline()
    albumFavourites = list(map(int,albumFavourites))

def writeDefaults():
    # config file : radio_stn, gapless, volume, Track_No, player_mode, auto_start
    global radio_stn, gapless, volume, Track_No, player_mode, auto_start, config_file
    defaults = [radio_stn, gapless, volume, Track_No, player_mode, auto_start]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)




# check config file exists, if not then write default values
config_file = "OLEDconfig.txt"
if not os.path.exists(config_file):
    writeDefaults()

# read config file : radio_stn, gapless, volume, Track_No, player_mode, auto_start
config = []
with open(config_file, "r") as file:
   line = file.readline()
   while line:
      config.append(line.strip())
      line = file.readline()
config = list(map(int,config))


radio_stn  = config[0]
gapless    = config[1]
volume     = config[2]
Track_No   = config[3]
player_mode = config[4] # 0 = Album Favs, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
auto_start = config[5]

if auto_start:
    if player_mode == 3:  # radio
        MP3_Play   = 0
        radio = 1
    else:
        MP3_Play   = 1
        radio = 0

trackHistory = []
albumFavourites = []


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
atimer      = time.monotonic()
played_pc   = 0
synced      = 0
reloading   = 0
abort_sd    = 1
usb_found   = 0



# find username
h_user  = []
h_user.append(myUsername)   # os.getlogin() not always working when script run automatically

favouritesIndex = 0

def getTrack(trackNum):
    global tracks
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[trackNum].split("/")
    trackData = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
    return trackData


def outputToDisplay(dispLine1,dispLine2,dispLine3,dispLine4):
    global image,top,width,height,font
    # Display image.
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((0, top + 0), dispLine1,  font=font, fill=255)
    draw.text((0, top + 8), dispLine2,  font=font, fill=255)
    draw.text((0, top + 16),dispLine3,  font=font, fill=255)
    draw.text((0, top + 24),dispLine4,  font=font, fill=255)
    disp.image(image)
    disp.display()

outputToDisplay("MP3 Player: v" + version, "", "", "")
time.sleep(2)
stop = 0
def reload():
  global tracks,Track_No,stop
  if stop == 0:
    tracks  = []
    outputToDisplay("Tracks: " + str(len(tracks),"Reloading tracks... ", "", "")
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
    Track_No = 0
    outputToDisplay("Tracks: " + str(len(tracks),"", "", "")
    if len(tracks) == 0:
        outputToDisplay("Tracks: " + str(len(tracks), "Stopped Checking")
        stop = 1
    time.sleep(1)


def loadTrackDictionaries():
    global tracks, albumDictionary, artistDictionary, albumList, artistList
    albumList = []    #   list of all albums in order    Because album names might not be unique, format is "AlbumName - Artist"
    artistList = []   #   list of all artists in order
    albumDictionary = {}   #  key is album ("AlbumName - Artist"), value is (first track number, last track number)
    artistDictionary = {}   #  key is artist, value is (first track number, last track number)
    currentArtist = ""
    currentArtistFirst = 0
    currentArtistLast = 0
    currentAlbum = ""
    currentAlbumFirst = 0
    currentAlbumLast = 0
    for trackNum in range(0,len(tracks)):
        ( artist, album, song, path1, path2, path3, path4 ) = tracks[trackNum].split("/")
        uniqAlbum = album + " - " + artist   # Because album names might not be unique, format is "AlbumName - Artist"
        if artist not in artistList:
            artistList.append(artist)
        if uniqAlbum not in albumList:
            albumList.append(uniqAlbum)
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
    ( artist, album, song, path1, path2, path3, path4 ) = tracks[trackNum].split("/")
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

def getAlbumTracksInfo(trackNum):
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    numRemainingTracks = currentAlbumLast - trackNum
    currentTrack = (trackNum - currentAlbumFirst) + 1
    return ( numRemainingTracks, currentTrack )

def getRemainingAlbumTime(trackNum):
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    timeRemaining = 0
    for trackCounter in range(trackNum,currentAlbumLast):
        trackDetails = getTrack(trackCounter)
        audio = MP3(trackDetails)
        timeRemaining += audio.info.length
    return timeRemaining

def goToNextAlbum(trackNum):
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    nextAlbumStart = currentAlbumLast + 1
    if nextAlbumStart > len(tracks):
        nextAlbumStart = 0
    return nextAlbumStart

def goToNextArtist(trackNum):
    ( currentArtistFirst, currentArtistLast) = getArtistStartFinish(trackNum)
    nextArtistStart = currentArtistLast + 1
    if nextArtistStart > len(tracks):
        nextArtistStart = 0
    return nextArtistStart

def goToPrevAlbum(trackNum):
    ( currentAlbumFirst, currentAlbumLast) = getAlbumStartFinish(trackNum)
    prevAlbumEnd = currentAlbumFirst - 1
    if prevAlbumEnd > 0:
        ( prevAlbumFirst, prevAlbumLast) = getAlbumStartFinish(prevAlbumEnd)
    else:
        prevAlbumFirst = 0
    return prevAlbumFirst

def goToPrevArtist(trackNum):
    ( currentArtistFirst, currentArtistLast) = getArtistStartFinish(trackNum)
    prevArtistEnd = currentArtistFirst - 1
    if prevArtistEnd > 0:
        ( prevArtistFirst, prevArtistLast) = getArtistStartFinish(prevArtistEnd)
    else:
        prevArtistFirst = 0
    return prevArtistFirst

def goToRandomAlbum():
    global albumList, albumDictionary
    numAlbums = len(albumList)
    selectedAlbumNum = random.randint(0, numAlbums - 1)
    selectedAlbum = albumList[selectedAlbumNum]
    ( currentAlbumFirst, currentAlbumLast) = albumDictionary[selectedAlbum]
    return currentAlbumFirst

def goToRandomTrack():
    global tracks
    selectedTrackNum = random.randint(0, len(tracks) - 1)
    return selectedTrackNum

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


def goToNextFavourite():
    global favouritesIndex, albumDictionary, albumList
    if len(albumFavourites) > 0:
        nextFav = albumFavourites[favouritesIndex]
        nextUniqAlbum = albumList[nextFav]
        ( favAlbumFirst, favAlbumLast) = albumDictionary[nextUniqAlbum]
        favouritesIndex += 1
        return favAlbumFirst
    else:
        return 0

def selectNextTrack(trackNum):
    global tracks, player_mode, favouritesIndex
    # 0 = Album Favs, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
    # if Rand Tracks choose another track at random which is not in the history
    if player_mode == 2:
        trackNum = goToRandomTrack()                        
    # if Album Favs go to the next track in the album, if at last track, go to the next favourite, if no more favourites change to Album Rand
    elif player_mode == 0:
        if len(albumFavourites) == 0 or favouritesIndex > len(albumFavourites):  # we ran out of favourites, so switch to Album Rand
            favouritesIndex = 0
            player_mode == 1
        else:
            trackNum = goToNextFavourite()
    # if Album Rand go to the next track in the album, if at last track, go to a random album which is not in album history
    if player_mode == 1:
        (tracksRemaining, currentTrack ) = getAlbumTracksInfo(trackNum)
        print("Tracks Remaining: " + str(tracksRemaining))
        if tracksRemaining == 0: # finished playing album
            trackNum = goToRandomAlbum()
        else:
            trackNum = ( (trackNum + 1) % len(tracks) )
    return trackNum




def showTrackProgress(trackNum, playLabel, played_pc):    # ignore played_pc if = -1
    global player_mode
    (remainTracks, currentTrack) = getAlbumTracksInfo(trackNum)
    (dispLine2, dispLine3, dispLine4) = getSongDetails(trackNum)
    if player_mode == 2:
        track_n = str(trackNum + 1) + "     "
    else:
        track_n = str(currentTrack) + "/" + str(remainTracks)
    if played_pc != -1:
        progress = str(played_pc)[-2:] + "% "
    else:
        progress = ""
    dispLine1 = playLabel + " " + str(track_n)[0:5] + "  " + progress + playerStatus(player_mode)
    outputToDisplay(dispLine1, dispLine2, dispLine3, dispLine4)



def getAlbumNum(trackNum):
    global albumList
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    uniqAlbum = album + " - " + artist
    albumNum = albumList.index(uniqAlbum)
    return albumNum
    


        

def add_removeCurrentAlbumFavs(trackNum):
    global albumFavourites
    albumNum = getAlbumNum(trackNum)
    if albumNum in albumFavourites:
        indexToRemove = albumFavourites.index(albumNum) if albumNum in albumFavourites else -1
        if indexToRemove == -1:
            albumFavourites.append(albumNum)
            outputToDisplay("", "Album + to Favs", "", "")
            time.sleep(1)
        else:
            albumFavourites.remove(indexToRemove)
            outputToDisplay("", "Album - From Favs", "", "")
            time.sleep(1)
        writeFavourites()





def Set_Volume():
    global mixername,m,MP3_Play,radio,radio_stn,volume,gapless
    while buttonVOLUP.is_pressed:
        volume +=1
        volume = min(volume,100)
        m.setvolume(volume)
        outputToDisplay("Set Volume.. " + str(volume), "", "", "")
        os.system("amixer -D pulse sset Master " + str(volume) + "%")
        if mixername == "DSP Program":
            os.system("amixer set 'Digital' " + str(volume + 107))
    while buttonVOLDN.is_pressed:
        volume -=1
        volume = max(volume,0)
        m.setvolume(volume)
        outputToDisplay("Set Volume.. " + str(volume), "", "", "")
        os.system("amixer -D pulse sset Master " + str(volume) + "%")
        if mixername == "DSP Program":
            os.system("amixer set 'Digital' " + str(volume + 107))
    writeDefaults()



def playerStatus(player_mode):
    global gapless,sleep_timer
    txt = " "
    if player_mode == 0:   # 0 = Album Favs, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
        txt +="FV"
    elif player_mode == 1:
        txt +="AR"
    elif player_mode == 2:
        txt +="RT"
    else:
        txt +=" "
    if gapless == 1:
        txt +="G"
    else:
        txt +=" "
    if sleep_timer > 0:
        txt +="S"
    else:
        txt +=" "
    return txt


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

outputToDisplay("Tracks: " + str(len(tracks), "", "", "")


# check if USB mounted and find USB storage
if use_USB == 1:
    start = time.monotonic()
    outputToDisplay("Checking for USB", "", "", "")
    while time.monotonic() - start < usb_timer:
        usb = glob.glob("/media/" +  h_user[0] + "/*")
        usb_found = len(usb)
        outputToDisplay("Checking for USB", "Found: " + str(usb_found) + " USBs", str(int(usb_timer -(time.monotonic() - start))), "")
        time.sleep(1)
    outputToDisplay("Checking for USB", "", "", "")
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
        outputToDisplay("Checking for USB", "No USB Found !!", "", "")
        sd_tracks = glob.glob("/home/" + h_user[0] + "/Music/*/*/*.mp3")
        time.sleep(2)
        if len(sd_tracks) != len(tracks):
            reloading = 1
        outputToDisplay("Checking for USB", "", "", "")

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
    
# try reloading tracks if one selected not found
if len(tracks) > 0:
    track = getTrack(Track_No)
    if not os.path.exists (track) and usb_found > 0 and stop == 0:
        reload()

# populate albumDictionary, artistDictionary, albumList, artistList
loadTrackDictionaries()

# wait for internet connection
if radio == 1:
    outputToDisplay("Waiting for Radio...", "", "", "")
    time.sleep(10)
    q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] ,shell=False)
    outputToDisplay((Radio_Stns[radio_stn]), "", "", "")
    
else:
    (remainTracks, currentTrack) = getAlbumTracksInfo(Track_No)
    stimer = getRemainingAlbumTime(Track_No)    





showTrackProgress(Track_No, "STOP", -1)

if gapless == 0:
    gap = 0
else:
    gap = gaptime    
    


if len(tracks) > 0:
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

Track_No = selectNextTrack(Track_No)



while True:    
    #################################################
    ######       loop while stopped   ###############
    #################################################
    #print("MP3 Play: " + str(MP3_Play) + "   radio: " + str(radio))
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
        if time.monotonic() - timer1 > 3 and Disp_on == 1 and len(tracks) > 0:
            timer1 = time.monotonic()
            if xt < 2:
                showTrackProgress(Track_No, "STOP", -1) 
            elif xt == 2:
                outputToDisplay("Status...  "  +  playerStatus(player_mode), "", "", "")
            elif xt == 3 and show_clock == 1 and synced == 1:
                now = datetime.datetime.now()
                clock = now.strftime("%H:%M:%S")
                outputToDisplay(clock, "", "", "")
            elif xt == 4:
                outputToDisplay("Volume: " + str(volume), "", "", "")
            elif xt == 5 and sleep_timer != 0:
                time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                outputToDisplay("SLEEP: " + str(time_left) + " mins", "", "", "")
            else:
                xt +=1
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
                if vp == 0:
                    outputToDisplay(clock, "", "", "")
                elif vp == 1:
                    outputToDisplay("", clock, "", "")
                elif vp == 2:
                    outputToDisplay("", "", clock, "")
                elif vp == 3:
                    outputToDisplay("", "", "", clock)
                old_secs2 = secs

        # DISPLAY OFF timer
        if time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1:
            outputToDisplay("", "", "", "")
            Disp_on = 0

            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    outputToDisplay("", "SHUTDOWN in " + str(t), "", "")
                else:
                    outputToDisplay("", "STOPPING in " + str(t), "", "")
                if buttonFAVMODE.is_pressed or buttonPLAY.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    outputToDisplay("SHUTTING DOWN...", "", "", "")
                else:
                    outputToDisplay("STOPPING........", "", "", "")
                time.sleep(3)
                outputToDisplay("", "", "", "")
                sleep_timer = 0 
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
            else:
                showTrackProgress(Track_No, "STOP", -1)
            Disp_start = time.monotonic()




        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # PLAY               STOP                        | PLAY (MP3 / RADIO)   START PLAY FAVS 
        ######################################################################################

            
        # PLAY key while stopped
        if buttonPLAY.is_pressed:
            stopped = 0
            Disp_on = 1
            Disp_start = time.monotonic()
            timer1 = time.monotonic()
            album = 0
            outputToDisplay("", "HOLD 5s: Play Favs", "", "")
            sleep_timer = 0
            while buttonPLAY.is_pressed and time.monotonic() - timer1 < buttonHold:
                pass
            if time.monotonic() - timer1 < buttonHold and len(tracks) > 0:
                ## PUSH
                # player mode is radio
                if player_mode == 3:
                    q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
                    time.sleep(0.05)
                    outputToDisplay(Radio_Stns[radio_stn], "", "", "")
                    rs = Radio_Stns[radio_stn]
                    while buttonPLAY.is_pressed:
                        pass
                    time.sleep(1)
                    radio    = 1
                    MP3_Play = 0
                    writeDefaults()                
                # player mode is not radio
                else:
                    if player_mode == 0 or player_mode == 1:
                        (remainTracks, currentTrack) = getAlbumTracksInfo(Track_No)
                        stimer = getRemainingAlbumTime(Track_No) 
                    atimer = time.monotonic()
                    MP3_Play = 1
                    radio    = 0
                    writeDefaults()
            else:   # HOLD
                # player mode is not radio
                if player_mode != 3:
                    pass   # play from start of favourites


        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # NEXT              NEXT TRACK/RADIO - NEXT ALB | BROWSE NEXT ALB - BROWSE NEXT ARTIST 
        ######################################################################################
                
        # check NEXT key when stopped
        if buttonNEXT.is_pressed and len(tracks) > 1:
            Disp_on = 1
            time.sleep(0.2)
            showTrackProgress(Track_No, "STOP", -1)
            timer1 = time.monotonic()
            album = 1
            while buttonNEXT.is_pressed and time.monotonic() - timer1 < buttonHold:
                pass
            if time.monotonic() - timer1 < buttonHold and len(tracks) > 0:
                # PUSH
                Track_No = goToNextAlbum(Track_No)
            else:
                # HOLD
                Track_No = goToNextArtist(Track_No)
            showTrackProgress(Track_No, "STOP", -1)
            time.sleep(0.5)
            writeDefaults()
            Disp_start = time.monotonic()
            timer1 = time.monotonic()


        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # PREV              PREV TRACK/RADIO - PREV ALB | BROWSE PREV ALB - BROWSE PREV ARTIST 
        ######################################################################################

        # check PREV key when stopped
        if  buttonPREV.is_pressed and len(tracks) > 1:
            Disp_on = 1
            time.sleep(0.2)
            Track_No = goToPrevAlbum(Track_No)
            showTrackProgress(Track_No, "STOP", -1)
            timer1 = time.monotonic()
            album = 1
            while buttonPREV.is_pressed and time.monotonic() - timer1 < buttonHold:
                pass
            if time.monotonic() - timer1 < buttonHold and len(tracks) > 0:
                # PUSH
                Track_No = goToPrevAlbum(Track_No)
            else:
                # HOLD
                Track_No = goToPrevArtist(Track_No)
            showTrackProgress(Track_No, "STOP", -1)
            time.sleep(0.5)
            writeDefaults()
            Disp_start = time.monotonic()
            timer1 = time.monotonic()


        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # VOLDN             VOL DN                      | VOL DN
        # VOLUP             VOL UP                      | VOL UP 
        ######################################################################################


        # check for VOLUP or VOLDN key when stopped
        if buttonVOLUP.is_pressed or buttonVOLDN.is_pressed:
            if Disp_on == 0:
                Disp_on = 1
                Disp_start = time.monotonic()
                showTrackProgress(Track_No, "STOP", -1)
                time.sleep(0.5)
            Set_Volume()
            time.sleep(0.5)


                
        ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
        # FAVMODE           CURRENT ALB > FAV ADD - REM | ROTATE MODE Album Favs  Album Rand  Rand Tracks  Radio - HOLD10s = SHUTDOWN
        ######################################################################################
            
        # check for FAVMODE key when stopped
        if  buttonFAVMODE.is_pressed:
            if Disp_on == 0:
                Disp_on = 1
                Disp_start = time.monotonic()
                showTrackProgress(Track_No, "STOP", -1)
                time.sleep(0.5)
                outputToDisplay("", playerModeNames[player_mode] + "   " , "", "")
            timer1 = time.monotonic()
            while buttonFAVMODE.is_pressed and time.monotonic() - timer1 < buttonHold:
                pass
            if time.monotonic() - timer1 < buttonHold:
                ################
                # Rotate through Modes  !!!
                ##############
                player_mode += 1
                player_mode = ( player_mode % numModes )
                outputToDisplay("", playerModeNames[player_mode] + "   " , "", "")
                if player_mode == 0:   # Album Favs
                    radio = 0
                    MP3_play = 1
                    Track_No = selectNextTrack(Track_No)
                    writeDefaults()
                elif player_mode == 1:   # Album Rand
                    radio = 0
                    MP3_play = 1                   
                    Track_No = selectNextTrack(Track_No)
                    writeDefaults()
                elif player_mode == 2:   # Rand Tracks
                    radio = 0
                    MP3_play = 1                  
                    Track_No = selectNextTrack(Track_No)
                    writeDefaults()
                else:     # Radio
                    radio = 1
                    MP3_play = 0
                    q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn]] , shell=False)
                    outputToDisplay(Radio_Stns[radio_stn], "", "", "")
                    rs = Radio_Stns[radio_stn] + "               "[0:19]
                    writeDefaults()
                # SHUTDOWN IF PRESSED FOR 10 SECONDS
                sleep_timer +=900
                if sleep_timer > 7200:
                    sleep_timer = 0
                sleep_timer_start = time.monotonic()
                outputToDisplay("Set SLEEP.. " + str(int(sleep_timer/60)), "HOLD for 10 to SHUTDOWN ", "", "")
                time.sleep(0.25)
                while buttonFAVMODE.is_pressed:
                    sleep_timer +=900
                    if sleep_timer > 7200:
                         sleep_timer = 0
                    sleep_timer_start = time.monotonic()
                    outputToDisplay("Set SLEEP.. " + str(int(sleep_timer/60), "", "", "")
                    time.sleep(1)
                    if time.monotonic() - timer1 > 5:
                        outputToDisplay("", "SHUTDOWN in " + str(10-int(time.monotonic() - timer1), "", "")
                    if time.monotonic() - timer1 > 10:
                        # shutdown if pressed for 10 seconds
                        outputToDisplay("SHUTTING DOWN...", "", "", "")
                        time.sleep(2)
                        outputToDisplay("", "", "", "")
                        MP3_Play = 0
                        radio = 0
                        time.sleep(1)
                        os.system("sudo shutdown -h now")
                showTrackProgress(Track_No, -1)
                timer1 = time.monotonic()
                xt = 2
            
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
            outputToDisplay("", "", "", "")
            Disp_on = 0

            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            Disp_start = time.monotonic()
            abort_sd = 0
            t = 30
            Disp_on = 1
            while t > 0 and abort_sd == 0:
                if sleep_shutdn == 1:
                    outputToDisplay("", "SHUTDOWN in " + str(t), "", "")
                else:
                    outputToDisplay("", "STOPPING in " + str(t), "", "")
                if buttonFAVMODE.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    outputToDisplay("SHUTTING DOWN...", "", "", "")
                else:
                    outputToDisplay("STOPPING........", "", "", "")
                time.sleep(1)
                outputToDisplay("", "", "", "")
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
        time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)]
        if sleep_timer > 0:
            shutdownMsg = "Shutdown: " + str(time_left) + "mins"
        else:
            shutdownMsg = ""
        if Disp_on == 1:
            if show_clock == 1 and synced == 1:
                outputToDisplay("", "      " + clock, shutdownMsg, "")
            else:
                outputToDisplay("", "", shutdownMsg, "")
        t = ""
        for r in range (0,random.randint(0,10)):
            t += " "
        clock = t + clock
        if show_clock == 1 and Disp_on == 0 and synced == 1:
            if secs != old_secs:
                if sleep_timer > 0:
                    clock = clock + " " + str(time_left)
                vp = random.randint(0,3)
                if vp == 0:
                    outputToDisplay(clock, "", "", "")
                elif vp == 1:
                    outputToDisplay("", clock, "", "")
                elif vp == 2:
                    outputToDisplay("", "", clock, "")
                elif vp == 3:
                    outputToDisplay("", "", "", clock)
                old_secs = secs
            
         # check for VOLDN  key
        if  buttonVOLDN.is_pressed :
            Disp_on = 1
            Disp_start = time.monotonic()
            outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            Set_Volume()
            time.sleep(0.5)
            timer1 = time.monotonic()

        # check for VOLUP key
        if  buttonVOLUP.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            Set_Volume()
            time.sleep(0.5)
            timer1 = time.monotonic()
                
        # check PREV key
        if buttonPREV.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            radio_stn -=2
            if radio_stn < 0:
               radio_stn = len(Radio_Stns) - 2
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            rs = Radio_Stns[radio_stn] + "               "[0:19]
            writeDefaults()
            timer1 = time.monotonic()
            
        # check NEXT key
        if buttonNEXT.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            radio_stn +=2
            if radio_stn > len(Radio_Stns)- 2:
               radio_stn = 0
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False))
            outputToDisplay(Radio_Stns[radio_stn], "", "", "")
            rs = Radio_Stns[radio_stn] + "               "[0:19]
            writeDefaults()
            timer1 = time.monotonic()
            time.sleep(0.5)
            
        # check PLAY (STOP Radio) key
        if buttonPLAY.is_pressed:
            Disp_on = 1
            Disp_start = time.monotonic()
            q.kill()
            radio = 0
            outputToDisplay("Radio Stopped      ", "", "", "")
            writeDefaults()
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
                    outputToDisplay("", "SHUTDOWN in " + str(t), "", "")
                else:
                    outputToDisplay("", "STOPPING in " + str(t), "", "")
                if buttonFAVMODE.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shutdn == 1:
                    outputToDisplay("SHUTTING DOWN...", "", "", "")
                else:
                    outputToDisplay("STOPPING........", "", "", "")
                time.sleep(0.05)
                time.sleep(3)
                Disp_on = 0
                outputToDisplay("", "", "", "")
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid, SIGTERM)
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
                sleep_timer = 0
                stopped = 1
                MP3_Play = 0
            else:
                outputToDisplay("Play.." + str(track_n)[0:5] + playerStatus(player_mode), "", "", "")
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
            rpistr = "mplayer " + " -quiet " +  '"' + track + '"'
            if Disp_on == 1:
                showTrackProgress(Track_No, "PLAY", played_pc)
            audio = MP3(track)
            track_len = audio.info.length
            # add track to history
            if trackHistory:
                trackHistoryLast = len(trackHistory) -1
                if Track_No != trackHistory[trackHistoryLast]:
                    trackHistory.append(Track_No)
            else:
                trackHistory.append(Track_No)
            p = subprocess.Popen(rpistr, shell=True, preexec_fn=os.setsid)
            poll = p.poll()
            while poll != None:
              poll = p.poll()
            timer1 = time.monotonic()
            xt = 0
            goToNextTrack = 1
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
                        if vp == 0:
                            outputToDisplay(clock, "", "", "")
                        elif vp == 1:
                            outputToDisplay("", clock, "", "")
                        elif vp == 2:
                            outputToDisplay("", "", clock, "")
                        elif vp == 3:
                            outputToDisplay("", "", "", clock)
                        old_secs2 = secs
                  
                time.sleep(0.2)
  
                played  = time.monotonic() - timer1
                played_pc = int((played/track_len) *100)
  
                # DISPLAY OFF timer
                if time.monotonic() - Disp_start > Disp_timer and Disp_timer > 0 and Disp_on == 1:
                    outputToDisplay("", "", "", "")
                    Disp_on = 0

             
                # display titles, status etc
                if time.monotonic() - timer1 > 2 and Disp_on == 1:
                    timer1    = time.monotonic()
                    played_pc =  "     " + str(played_pc)
                    if xt < 2:
                        showTrackProgress(Track_No, "PLAY", played_pc)
                    elif xt == 2:
                        outputToDisplay("Status...  " +  playerStatus(player_mode), "", "", "")
                    elif xt == 4 and sleep_timer != 0:
                        time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                        outputToDisplay("SLEEP: " + str(time_left) + " mins", "", "", "")
                    elif xt == 5 and show_clock == 1 and synced == 1:
                        now = datetime.datetime.now()
                        clock = now.strftime("%H:%M:%S")
                        outputToDisplay(clock, "", "", "")
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
                        outputToDisplay(" " + str(pmin) + ":" + str(psec2) + " of " + str(lmin) + ":" + str(lsec2), "", "", "")
                    xt +=1
                    if xt > 5:
                        xt = 0
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # PLAY               STOP                        | PLAY (MP3 / RADIO)   START PLAY FAVS 
                ######################################################################################
                      
                # check for PLAY (STOP) key when playing MP3
                if buttonPLAY.is_pressed:
                    Disp_on = 1
                    Disp_start = time.monotonic()
                    timer1 = time.monotonic()
                    os.killpg(p.pid, SIGTERM)
                    outputToDisplay("Track Stopped", "", "", "")
                    time.sleep(2)
                    showTrackProgress(Track_No, "STOP", -1)
                    goToNextTrack = 0
                    MP3_Play = 0
                    writeDefaults()
  
  
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # NEXT              NEXT TRACK/RADIO - NEXT ALB | BROWSE NEXT ALB - BROWSE NEXT ARTIST 
                ######################################################################################
  
                  
                # check for NEXT key when playing MP3
                if buttonNEXT.is_pressed:
                    Disp_on = 1
                    Disp_start = time.monotonic()
                    os.killpg(p.pid, SIGTERM)
                    # add current track number to history, if not already last item
                    Track_No = selectNextTrack(Track_No)
                    showTrackProgress(Track_No, "PLAY", -1)
                    time.sleep(0.5)
                    goToNextTrack = 0
  
  
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # PREV              PREV TRACK/RADIO - PREV ALB | BROWSE PREV ALB - BROWSE PREV ARTIST 
                ######################################################################################
                  
                # check for PREV key when playing MP3
                if buttonPREV.is_pressed:
                    Disp_on = 1
                    Disp_start = time.monotonic()
                    Disp_on = 1
                    os.killpg(p.pid, SIGTERM)
                    if trackHistory:
                        trackHistoryLast = len(trackHistory) -1
                        if len(trackHistory) > 0:
                            Track_No = trackHistory.pop(trackHistoryLast)   # use last item in track history then remove it
                            showTrackProgress(Track_No, "PLAY", -1)
                            time.sleep(0.5)
                            goToNextTrack = 0
  
  
  
  
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # VOLDN             VOL DN                      | VOL DN
                # VOLUP             VOL UP                      | VOL UP 
                ######################################################################################
  
  
                # check for VOLDN or VOLDN key when playing MP3
                if buttonVOLUP.is_pressed or buttonVOLDN.is_pressed:
                    if Disp_on == 0:
                        Disp_on = 1
                        Disp_start = time.monotonic()
                        showTrackProgress(Track_No, "PLAY", played_pc)
                        time.sleep(0.5)
                    Set_Volume()
                    time.sleep(0.5)
  
                ##############      WHILE PLAYING PUSH - HOLD   |  WHILE STOPPED PUSH - HOLD
                # FAVMODE           CURRENT ALB > FAV ADD - REM | ROTATE MODE Album Favs  Album Rand  Rand Tracks  Radio - HOLD10s = SHUTDOWN
                ######################################################################################
                             
                # check for FAVMODE key when playing MP3
                if buttonFAVMODE.is_pressed:
                    if Disp_on == 0:
                        Disp_start = time.monotonic()
                        Disp_on = 1
                        showTrackProgress(Track_No, "PLAY", played_pc)
                        time.sleep(1)
                    Disp_on = 1
                    timer1 = time.monotonic()
                    while buttonFAVMODE.is_pressed and time.monotonic() - timer1 < buttonHold:
                        pass
                    if time.monotonic() - timer1 < buttonHold and len(tracks) > 0:
                        # PUSH
                        # add current album to favourites
                        add_removeCurrentAlbumFavs(Track_No)
  
                  
                poll = p.poll()
            
            if goToNextTrack == 1:
                Track_No = selectNextTrack(Track_No)
        





            
