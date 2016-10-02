#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import traceback
import cv2
import numpy
import math
import logging
import socket
import threading
import time
import datetime

from ImageProcessor import ImageProcessor

class CarControl(object):
    def __init__(self, carnumber):
        self.client_socket = None
        self.latestimage = None
        self.controlthread = None
        self.process = True
        self.carnumber = carnumber
        self.targetspeed = 0
        self.targetlane = 0
        self.racestarted = False
        self.lapcount = 0
        self.logger = logging.getLogger('formulapi')
        self.imgprocess = ImageProcessor()

    def ConnectToSimulator(self):
        self.logger.info('Connect to simulator')
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(("localhost", 8000))
    
    def GetImage(self):
        if not self.client_socket:
            raise AssertionError('Must connect to simulator !!!')
        starttime = datetime.datetime.now()
        self.client_socket.send('capture %d' % self.carnumber)
        size = self.client_socket.recv(1024)
        size = int(size)
        self.client_socket.send('go')
        image = ''
        while len(image) != size:
            image += self.client_socket.recv(size)
        #self.logger.debug('receive image : size %d' % len(image))
        #self.logger.debug("getimage duration %s" % (datetime.datetime.now()-starttime) )
        x = numpy.fromstring(image, dtype='uint8')
        self.latestimage = cv2.imdecode(x, cv2.IMREAD_UNCHANGED)
        return self.latestimage

    def AdjustMotorSpeed(self, angle):
        # speed in percentage 0:100 -> 0:2m/s
        speed = self.targetspeed
        # we adjust
        left = speed/100. * 2
        right = speed/100. * 2
        if angle < 0:
            # increase right speed to turn left
            right = right * (1+ abs(angle)/90.) 
        else:
            # increase left speed to turn right
            left = left * (1+ abs(angle)/90.) 
        # send command to simulator
        self.client_socket.send('motor %d %f %f' % (self.carnumber, left, right))

    def Start(self):
        self.logger.info('Start control')
        self.ConnectToSimulator()
        #run thread
        self.logger.info('Start control thread')
        self.controlthread = threading.Thread(target=self.Run)
        self.controlthread.daemon = True
        self.controlthread.start()

    def Run(self):
        """
        get image
        process image
        set cap and speed
        """
        self.logger.info('Run control')
        while self.process:
            #to have 10 images per sec
            time.sleep(0.1)
            try:
                image = self.GetImage()
                self.imgprocess.ProcessingImage(image)
            except:
                try:
                    exc_info = sys.exc_info()

                    # do you usefull stuff here
                    # (potentially raising an exception)
                    try:
                        #stop race and exit
                        self.lapcount = 100
                    except:
                        pass
                    # end of useful stuff
                finally:
                    # Display the *original* exception
                    traceback.print_exception(*exc_info)
                    del exc_info
                return
            
            if self.racestarted:
                position = self.CurrentTrackPosition()
                #negative => go right, positive => go left
                angle = self.CurrentAngle() # degree
                curve = self.CurrentAngle()
                #simple process - follow lane
                K = 90 / 3.
                cap = K*(position - self.targetlane)
                consigne = cap
                print 'position,consigne,angle,curve',position,consigne,angle,curve
                self.AdjustMotorSpeed(consigne)
                    
    def Stop(self):
        self.logger.info('Stop control')
        self.Speed(0)
        self.AdjustMotorSpeed(0)
        time.sleep(1)
        self.client_socket.close()
        # terminate run thread
        self.process = False
        #wait for terminate
        self.controlthread.join(5)
        #reset var
        self.controlthread = None
        
    def Speed(self, speed):
        #self.logger.debug('Set speed to %r' % speed)
        self.targetspeed = speed

    def AimForLane(self, position):
        self.logger.debug('AimForLane %r' % position)
        self.targetlane = position

    def TrackCurve(self):
        return self.imgprocess.trackcurve
    
    def CurrentTrackPosition(self):
        return self.imgprocess.trackoffset

    def TrackFound(self):
        if self.imgprocess.trackoffset is None:
            self.logger.info('Track not found')
            return False
        else:
            self.logger.info('Track found')
            return True
    
    def CurrentAngle(self):
        return self.imgprocess.angle

    def GetLatestImage(self):
        return self.latestimage

    def LapCount(self):
        return self.lapcount
