#!/usr/bin/python

import sys
import os
from gpiozero import Button
import time
from subprocess import Popen, PIPE, CalledProcessError
from multiprocessing import Process
from multiprocessing import Queue
from queue import Empty

mplayer = "/usr/bin/mplayer"



fifo_file = "/tmp/mplayer-%d" % (time.time())
os.mkfifo(fifo_file)


# GPIO BUTTONS GPIO BCM numbers (Physical pin numbers)

PLAY   = 12  
NEXT   = 7 
PREV   = 20 


buttonPREV  = Button(PREV)
buttonPLAY  = Button(PLAY)
buttonNEXT  = Button(NEXT)

def mplayerCommand(someCommand):
    with open(fifo_file, 'w') as fifo:
        fifo.write(someCommand)

def mplayer_play(queue):
    cmd = [mplayer, '-slave',  '-playlist', '/home/philip/temp_playlist.txt','-input'  ,'file=%s' % (fifo_file)] 

    playCounter = 0

    with Popen(cmd, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            playCounter += 1
            #print(line, end='') # process line here
            if "Playing" in str(line):
                statusString = "EVENT: playing"
                queue.put(statusString)
            if "A:  " in str(line):
                if ((playCounter % 20) == 0):
                    timeElapsed = line.split()[1]
                    statusString = "Time Elapsed: " + str(timeElapsed)
                    queue.put(statusString)

def pullValueFromQ(queue):
    try:
        item = queue.get(timeout=0.1)
    except Empty:
        return ""
    return item

def main():

    statusQueue = Queue()

    mplayer_process = Process(target=mplayer_play, args=(statusQueue,))
    mplayer_process.start()

    while True:
        statusMplayer = pullValueFromQ(statusQueue)
        if statusMplayer:
            print(statusMplayer)
        if buttonPLAY.is_pressed:
            mplayerCommand("stop\n")
            break

        if buttonNEXT.is_pressed:
            mplayerCommand("pt_step 1\n")
                
        if buttonPREV.is_pressed:
            mplayerCommand("pt_step -1\n")        

    mplayer_process.join()



if __name__ == '__main__':
    main()
# vim: expandtab
