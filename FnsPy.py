
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

import VarsGlobal

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

albumList = []    #   list of all albums in order    Because album names might not be unique, format is "AlbumName - Artist"
artistList = []   #   list of all artists in order
albumDictionary = {}   #  key is album ("AlbumName - Artist"), value is (first track number, last track number)
artistDictionary = {}   #  key is artist, value is (first track number, last track number)

tracks = None

def getNumTracks():
    return len(tracks)

def getTrack(trackNum):
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[trackNum].split("/")
    trackData = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
    return trackData


def outputToDisplay(dispLine1,dispLine2,dispLine3,dispLine4):
    # Display image.
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((0, top + 0), dispLine1,  font=font, fill=255)
    draw.text((0, top + 8), dispLine2,  font=font, fill=255)
    draw.text((0, top + 16),dispLine3,  font=font, fill=255)
    draw.text((0, top + 24),dispLine4,  font=font, fill=255)
    disp.image(image)
    disp.display()

def outputToDisplayFlashing(dispLine1,dispLine2,dispLine3,dispLine4):
    numberFlashes = 5
    while numberFlashes:
        numberFlashes -= 1
        outputToDisplay("", "", "", "")
        time.sleep(0.2)
        outputToDisplay(dispLine1,dispLine2,dispLine3,dispLine4)
        time.sleep(0.2)
    time.sleep(1)

def outputToDisplayRand(dispText):
    vp = random.randint(0,3)
    if vp == 0:
        outputToDisplay(dispText, "", "", "")
    elif vp == 1:
        outputToDisplay("", dispText, "", "")
    elif vp == 2:
        outputToDisplay("", "", dispText, "")
    elif vp == 3:
        outputToDisplay("", "", "", dispText)

def reload(stop):
  if stop == 0:
    tracks  = []
    outputToDisplay("Tracks: " + str(len(tracks)),"Reloading tracks... ", "", "")
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
    with open(baseDir + "/tracks.txt", 'w') as f:
        for item in tracks:
            f.write("%s\n" % item)
    Track_Num = 0
    outputToDisplay("Tracks: " + str(len(tracks)),"", "", "")
    if len(tracks) == 0:
        outputToDisplay("Tracks: " + str(len(tracks)), "Stopped Checking")
        stop = 1
    time.sleep(1)
    return Track_Num

def loadTrackDictionaries():
    global albumDictionary, artistDictionary, albumList, artistList

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
    selectedTrackNum = random.randint(0, len(tracks) - 1)
    return selectedTrackNum

def getSongDetails(trackNum):
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    out1 = artist[0:19]
    out2 = album[0:19]
    out3 = song[0:19]
    try:
        if int(song[0:2]) > 0:
            out3 = song[3:22]
    except:
        pass
    return ( out1, out2, out3)

def getSingleLineSongDetails(trackNum):
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    return song[0:18]


def goToNextFavourite():
    global favouritesIndex, albumDictionary, albumList
    debugMsg("NEXT Fav starting index: " + str(favouritesIndex))
    if len(albumFavourites) > 0:
        nextFav = albumFavourites[favouritesIndex]
        nextUniqAlbum = albumList[nextFav]
        ( favAlbumFirst, favAlbumLast) = albumDictionary[nextUniqAlbum]
        favouritesIndex = (favouritesIndex + 1) % len(albumFavourites)
        debugMsg("NEXT Fav finishing index: " + str(favouritesIndex))
        return favAlbumFirst
    else:
        return 0

def goToPrevFavourite():
    global favouritesIndex, albumDictionary, albumList
    debugMsg("PREV Fav starting index: " + str(favouritesIndex))
    # favouritesIndex is +1 from currently playing favourite
    if len(albumFavourites) > 0:
        if favouritesIndex > 1:
            favouritesIndex = favouritesIndex - 2
        else:
            favouritesIndex = 0
        prevFav = albumFavourites[favouritesIndex]
        prevUniqAlbum = albumList[prevFav]
        ( favAlbumFirst, favAlbumLast) = albumDictionary[prevUniqAlbum]
        favouritesIndex = (favouritesIndex + 1) % len(albumFavourites)
        debugMsg("PREV Fav finishing index: " + str(favouritesIndex))
        return favAlbumFirst
    else:
        return 0

def selectNextTrack(trackNum):
    global player_mode, favouritesIndex, activeTrack, start_time, playFavourites
    # 0 = Album, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
    # if Rand Tracks choose another track at random which is not in the history
    debugMsg("NEXT Player Mode: " + str(player_mode))
    debugMsg("NEXT Supplied Track Num: " + str(trackNum))
    newTrackSelected = False
    if player_mode == 2:
        trackNum = goToRandomTrack()
        newTrackSelected = True
    elif player_mode == 0 or player_mode == 1:
        # if playing favourites, carry on
        if playFavourites:
            if len(albumFavourites) == 0 or favouritesIndex >= len(albumFavourites):  # we ran out of favourites
                favouritesIndex = 0
                newTrackSelected = False
                playFavourites = False
            else:
                (tracksRemaining, currentTrack ) = getAlbumTracksInfo(trackNum)
                debugMsg("P0 Tracks Remaining: " + str(tracksRemaining))
                if tracksRemaining == 0: # finished playing album
                    trackNum = goToNextFavourite()
                else:
                    trackNum = ( (trackNum + 1) % len(tracks) )
                newTrackSelected = True
        if not newTrackSelected:
            # if in doubt go to the next track in the album, if at last track, go to next or random album depending on mode
            (tracksRemaining, currentTrack ) = getAlbumTracksInfo(trackNum)
            debugMsg("P1 Tracks Remaining: " + str(tracksRemaining))
            if tracksRemaining == 0: # finished playing album
                if player_mode == 0:
                    trackNum = ( (trackNum + 1) % len(tracks) )   # go to next album in file seq
                elif player_mode == 1:
                    trackNum = goToRandomAlbum()   # choose rand album
            else:
                trackNum = ( (trackNum + 1) % len(tracks) )                    
    debugMsg("NEXT New Track Num: " + str(trackNum))
    activeTrack = trackNum
    debugMsg("activeTrack: " + str(activeTrack))
    start_time = 0
    return trackNum

def addToTrackHistory(trackNum):
    global trackHistory
    debugMsg("Starting Track History:")
    debugMsg(trackHistory)
    if trackHistory:
        trackHistoryLast = len(trackHistory) -1
        if trackNum != trackHistory[trackHistoryLast]:
            trackHistory.append(trackNum)
    else:
        trackHistory.append(trackNum)
    debugMsg("New Track History:")
    debugMsg(trackHistory)

def selectPrevTrack(trackNum):
    global trackHistory, player_mode
    debugMsg("PREV Player Mode: " + str(player_mode))
    debugMsg("PREV Supplied Track Num: " + str(trackNum))
    # 0 = Album, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
    # if in rand tracks use and remove the penultimate track from history    
    if player_mode == 2 and trackHistory:
        trackHistoryLast = len(trackHistory) -1
        trackNum = trackHistory.pop(trackHistoryLast) # ignore the final entry since that will be the current track
        trackHistoryLast = len(trackHistory) -1
        if len(trackHistory) > 0:
            trackNum = trackHistory.pop(trackHistoryLast)   # use last item in track history then remove it
            debugMsg("PREV New Track Num: " + str(trackNum))
            return trackNum
    # otherwise, if in doubt just go to the previous track on file    
    maxTrack = len(tracks) - 1
    trackNum = ( trackNum -1 ) % maxTrack
    return trackNum

def getPlayDuration(TrackNum, startTimer):
    global start_time
    track_len = getTrackLen(TrackNum)
    timeNow = time.monotonic()
    played  = int(timeNow - startTimer)    # time duration since last pressed play (not since start of track)
    Totalplayed  = start_time + played
    played_pc = int((Totalplayed/track_len) *100)
    debugMsg("getPlayDuration: track_len: " + str(track_len))
    debugMsg("getPlayDuration: timeNow: " + str(timeNow))
    debugMsg("getPlayDuration: played: " + str(played))
    debugMsg("getPlayDuration: startTimer: " + str(startTimer))
    debugMsg("getPlayDuration: played_pc: " + str(played_pc))
    return (played, played_pc, track_len)                            


def showTrackProgress(trackNum, playLabel, played_pc):    # ignore played_pc if = -1
    global player_mode
    (remainTracks, currentTrack) = getAlbumTracksInfo(trackNum)
    (dispLine2, dispLine3, dispLine4) = getSongDetails(trackNum)
    totalTracks = currentTrack + remainTracks
    if player_mode == 2:
        track_n = str(trackNum + 1) + "     "
    else:
        track_n = str(currentTrack) + "/" + str(totalTracks)
    if played_pc != -1:
        progress = str(played_pc)[-2:] + "% "
    else:
        progress = ""
    dispLine1 = playLabel + " " + str(track_n)[0:5] + "  " + progress + playerStatus(player_mode)
    outputToDisplay(dispLine1, dispLine2, dispLine3, dispLine4)

def showTrackProgressEDIT(trackNum, playLabel, startTimer):
    (played, played_pc, track_len) = getPlayDuration(trackNum, startTimer)
    showTrackProgress(trackNum, playLabel, played_pc)

def getRemainingTime(trackNum, startTimer):
    (played, played_pc, track_len) = getPlayDuration(trackNum, startTimer)
    remainingTime = track_len - played
    return remainingTime

def getPlayedTime(trackNum, startTimer):
    (played, played_pc, track_len) = getPlayDuration(trackNum, startTimer)
    debugMsg("Played Time: " + str(played))
    return played

def getAlbumNum(trackNum):
    global albumList
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    uniqAlbum = album + " - " + artist
    albumNum = albumList.index(uniqAlbum)
    return albumNum

def getArtistNum(trackNum):
    global artistList
    ( artist, album, song ) = getArtistAlbumSongNames(trackNum)
    artistNum = artistList.index(artist)
    return artistNum

def displayTrackList(trackNum):
    maxTrack = len(tracks) - 1
    trackNumDec1 = ( trackNum -1 ) % maxTrack
    trackNum = trackNum % maxTrack
    trackNumInc1 = ( trackNum + 1 ) % maxTrack
    trackNumInc2 = ( trackNum + 2 ) % maxTrack
    outputToDisplay(" " + getSingleLineSongDetails(trackNumDec1),getSingleLineSongDetails(trackNum)," " + getSingleLineSongDetails(trackNumInc1)," " + getSingleLineSongDetails(trackNumInc2))
    
def displayAlbumList(albumNumber):
    global albumList
    maxAlbum = len(albumList)
    albumNumberDec1 = ( albumNumber -1 ) % maxAlbum
    albumNumber = albumNumber % maxAlbum
    albumNumberInc1 = ( albumNumber + 1 ) % maxAlbum
    albumNumberInc2 = ( albumNumber + 2 ) % maxAlbum
    outputToDisplay(" " + albumList[albumNumberDec1],albumList[albumNumber]," " + albumList[albumNumberInc1]," " + albumList[albumNumberInc2])
    
def displayArtistList(artistNumber):
    global artistList
    maxArtist = len(artistList)
    artistNumberDec1 = ( artistNumber -1 ) % maxArtist
    artistNumber = artistNumber % maxArtist
    artistNumberInc1 = ( artistNumber + 1 ) % maxArtist
    artistNumberInc2 = ( artistNumber + 2 ) % maxArtist
    outputToDisplay(" " + artistList[artistNumberDec1],artistList[artistNumber]," " + artistList[artistNumberInc1]," " + artistList[artistNumberInc2])

def browseMusic(trackNum, browseMode, deltaValue):
    global albumList, artistList, albumDictionary, artistDictionary
    if browseMode == "Track":
        trackNum = ( trackNum + deltaValue ) % len(tracks)
        displayTrackList(trackNum)
        return trackNum
    if browseMode == "Album":
        albumNumber = getAlbumNum(trackNum)
        albumNumber = ( albumNumber + deltaValue ) % len(albumList)
        displayAlbumList(albumNumber)
        albumName = albumList[albumNumber]
        (albumStart, albumFinish) = albumDictionary[albumName]
        return albumStart
    if browseMode == "Artist":
        artistNumber = getArtistNum(trackNum)
        artistNumber = ( artistNumber + deltaValue ) % len(artistList)
        displayArtistList(artistNumber)
        artistName = artistList[artistNumber]
        (artistStart, artistFinish) = artistDictionary[artistName]
        return artistStart

def add_removeCurrentAlbumFavs(trackNum):
    global albumFavourites
    albumNum = getAlbumNum(trackNum)
    indexToRemove = albumFavourites.index(albumNum) if albumNum in albumFavourites else -1
    debugMsg("indexToRemove: " + str(indexToRemove))
    if indexToRemove == -1:
        albumFavourites.append(albumNum)
        outputToDisplayFlashing("", "Album + to Favs", "", "")
        debugMsg("Album: " + str(albumNum) + " added to Favourites")
        debugMsg(albumFavourites)
    else:
        albumFavourites.remove(albumNum)
        outputToDisplayFlashing("", "Album - From Favs", "", "")
        debugMsg("Album: " + str(albumNum) + " removed from Favourites")
        debugMsg(albumFavourites)
    outputToDisplay("", "", "", "")
    writeFavourites()

def getTrackLen(TrackNum):
    track = getTrack(TrackNum)
    audio = MP3(track)
    track_len = audio.info.length
    return track_len



def playMP3(TrackNum):
    global start_time, activeTrack
    track_len = getTrackLen(TrackNum)
    debugMsg("playMP3: activeTrack: " + str(activeTrack))
    debugMsg("playMP3: TrackNum: " + str(TrackNum))
    if start_time > track_len:
        start_time = 0
    if activeTrack != TrackNum:
        start_time = 0
        activeTrack = TrackNum
    track = getTrack(TrackNum)
    debugMsg("playMP3: track: " + str(track))
    debugMsg("playMP3: start_time: " + str(start_time))
    debugMsg("playMP3: new activeTrack: " + str(activeTrack))
    rpistr = "mplayer -ss " + str(start_time) + " -quiet " +  '"' + track + '"'
    addToTrackHistory(TrackNum)
    p = subprocess.Popen(rpistr, shell=True, preexec_fn=os.setsid)
    return p


def Set_Volume():
    global mixername,m,MP3_Play,radio,radio_stn,volume,gapless
    while buttonVOLUP.is_pressed and not buttonVOLDN.is_pressed:
        volume +=1
        volume = min(volume,100)
        m.setvolume(volume)
        outputToDisplay("Set Volume.. " + str(volume), "", "", "")
        os.system("amixer -D pulse sset Master " + str(volume) + "%")
        if mixername == "DSP Program":
            os.system("amixer set 'Digital' " + str(volume + 107))
    while buttonVOLDN.is_pressed and not buttonVOLUP.is_pressed:
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
    if player_mode == 0:   # 0 = Album, 1 = Album Rand, 2 = Rand Tracks, 3 = Radio
        txt +="AL"
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

def get_dir_size(dir_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(dir_path):
        for file in filenames:
            file_path = os.path.join(dirpath, file)
            if not os.path.islink(file_path):
                total_size += os.path.getsize(file_path)
    return total_size

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = ""
    finally:
        s.close()
    return IP
    
def debugMsg( msgString ):
    if debugOut:
        print(msgString)

def writeFavourites():
    global favourites_file, albumFavourites
    with open(favourites_file, 'w') as f:
        for item in albumFavourites:
            f.write("%s\n" % item)

def writeDefaults(defaults):
    # config file : radio_stn, gapless, volume, Track_No, player_mode, auto_start
    #global radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time
    #defaults = [radio_stn, gapless, volume, Track_No, player_mode, auto_start, start_time]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)
