#!/usr/bin/python

import sys
import os
import json
import argparse
import time
from subprocess import Popen, PIPE, CalledProcessError

mplayer = "/usr/bin/mplayer"

#parse_mplayer_output = lambda x: x.split("A:")[-1].split("V:")[0].strip()
parse_mplayer_output = lambda x: x.split("A:  ")[-1].split(" ")[0].strip()


def parse_args():
    parser = argparse.ArgumentParser(description='mplayer-resume')
    parser.add_argument('-r', '--resume', nargs=1, type=int, metavar='int', default=-2,
            help='time difference in seconds, negative number means a rollback')
    parser.add_argument('flags', nargs=argparse.REMAINDER, default=None,
            metavar='margs', help='mplayer arguments')

    return (vars(parser.parse_args()), parser)

def run_mplayer(args):
    fifo_file = "/tmp/mplayer-%d" % (time.time())
    os.mkfifo(fifo_file)
    cmd = [mplayer, '-slave',  '-playlist', '/home/philip/temp_playlist.txt','-input'  ,'file=%s' % (fifo_file)] + args
    print(cmd)

    with Popen(cmd, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            print(line, end='') # process line here

    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)



def main():
    args, parser = parse_args()
    resume = args['resume']
    if type(resume) == list: resume = resume[0]
    mflags = args['flags']
    file_name = None


    print(mflags)
    run_mplayer(mflags)


if __name__ == '__main__':
    main()
# vim: expandtab
