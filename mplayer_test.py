#!/usr/bin/python

import sys
import os
from gpiozero import Button
import time
from subprocess import Popen, PIPE, CalledProcessError

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


def main():

    cmd = [mplayer, '-slave',  '-playlist', '/home/philip/temp_playlist.txt','-input'  ,'file=%s' % (fifo_file)] 
    print(cmd)

    playCounter = 0

    with Popen(cmd, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            playCounter += 1
            #print(line, end='') # process line here
            if "Playing" in str(line):
                print("EVENT: playing")
            if "A:  " in str(line):
                if ((playCounter % 20) == 0):
                    timeElapsed = line.split()[1]
                    print("Time Elapsed: " + str(timeElapsed))
            if buttonPLAY.is_pressed:
                mplayerCommand("pause\n")

            if buttonNEXT.is_pressed:
                mplayerCommand(">")
                
            if buttonPREV.is_pressed:
                mplayerCommand("<")

    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)


if __name__ == '__main__':
    main()
# vim: expandtab
