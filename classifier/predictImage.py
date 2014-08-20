#!/bin/python

import common.log as logging
import common.config as Conf
import os, sys, signal, errno

from time import localtime
from datetime import datetime, date, timedelta, time
from re import search
from os import listdir, path, makedirs
from exceptions import RuntimeWarning
from warnings import simplefilter
from scipy import io
from shutil import move
import numpy
import Image
import sys
import errno

logger = logging.getLogger()

glbSunrise = [6, 10] # sub -20 mins
glbSunset = [18, 20] # add +30 mins
gDirectory = '/home/huanghst/workspace/GarageEye/data/'
glbSunfile='suntimes.txt'

# from
# http://www.janeriksolem.net/2009/06/histogram-equalization-with-python-and.html
def histeq(im,nbr_bins=256):
  #get image histogram
  imhist,bins = numpy.histogram(im.flatten(),nbr_bins,normed=True)
  cdf = imhist.cumsum() #cumulative distribution function
  cdf = 255 * cdf / cdf[-1] #normalize

  #use linear interpolation of cdf to find new pixel values
  im2 = numpy.interp(im.flatten(),bins[:-1],cdf)

  im2 = im2.reshape(im.shape)
  return numpy.matrix(im2, dtype=numpy.float64)


# sigmoid function
def sigmoid(z):
  onesMatrix = numpy.ones( z.shape )
  simplefilter("ignore", RuntimeWarning)
  rval = numpy.exp(-z)
  simplefilter("default", RuntimeWarning)
  rval = onesMatrix / (onesMatrix + rval)
#  rval = onesMatrix / (onesMatrix + numpy.exp(numpy.negative(z)))
#  print rval
  return rval

# load image
# assume the image is 640x480
# resize it to 320x240 and crop out the last 20 pixels
def loadImage(filename):
  im = Image.open(filename).convert("L")
  im = im.resize( (320, 240) )
  im = im.crop( (0,0, 320, 220) )
  return im


def predict(Theta1, Theta2, X):
# debug
#  print "running predict.m"
#  print Theta1.shape
#  print Theta2.shape
#  print X.shape
  m = X.shape[0]
  num_labels = Theta2.shape[0]
  onesMat = numpy.ones( (m, 1), dtype=numpy.float64 )
  h1 = sigmoid(numpy.dot (numpy.hstack((onesMat, X)), Theta1.T))
  h2 = sigmoid(numpy.dot (numpy.hstack((onesMat, h1)), Theta2.T))
  return h2

def dayPredict(filename):
  imageX = numpy.matrix(loadImage(filename), \
             dtype=numpy.float64)
  imageX = imageX.flatten('F')

  try:
    x=io.loadmat(gDirectory+'ThetasV7.mat', None, False)
  except:
    logger.error("Load mat failed")
    return 0

  Theta1 = x['Theta1']
  Theta2 = x['Theta2']
  confidence = predict(Theta1, Theta2, imageX)
  logger.info(filename + "\t(" + str(confidence[0,0]) + ")"),
  if (confidence[0,0] > 0.5):  logger.info("\t[closed]")
  if (confidence[0,0] <= 0.5):  logger.info("\t[opened]")
  return confidence

def nightPredict(filename):
  imageX = numpy.matrix(loadImage(filename), \
           dtype=numpy.float64)

# it's really really dark. 
  if (numpy.std(imageX.flatten('F')) < 1.0):
    logger.info(filename + "\t(0.99999999)"),
    logger.info("\t[closed]")
    return 0.999

  imageX = histeq(imageX)
# debug. uncomment to display image
#  Image.fromarray(imageX).show()
  imageX = imageX.flatten('F')

  x=io.loadmat(gDirectory+'NThetasV7.mat', None, False)
  Theta1 = x['Theta1']
  Theta2 = x['Theta2']
  confidence = predict(Theta1, Theta2, imageX)
  print filename + "\t(" + str(confidence[0,0]) + ")",
  if (confidence[0,0] > 0.5):  logger.info("\t[closed]")
  if (confidence[0,0] <= 0.5):  logger.info("\t[opened]")
  return confidence

# the format is always:
#   hhmm
# return int hour, int min, bool daytime
#   daytime = true if between sunrise and sunset time
#   daytime = false if between sunset and sunrise time
def extract_localtime(match):
  localtimeStr = match.group(2)
  hour = int(localtimeStr[0]+localtimeStr[1])
  minute = int(localtimeStr[2]+localtimeStr[3])
  dayTime = False
  if (hour*60+minute >= glbSunrise[0]*60+glbSunrise[1]) and \
     (hour*60+minute <= glbSunset[0]*60+glbSunset[1]):
    dayTime=True
  return (hour, min, dayTime) 

#
# make the path if it doesn't exist.
#
def make_sure_path_exists(path):
    try:
        makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

# look at the files in a directory and process each file as open or closed
# print out the results
def predict_pics(dirname):
  if path.exists(dirname)== False:
    print "directory does not exist"
    return

  filenames = listdir(dirname)
  for filename in filenames:
    if search(r"(.+)\.jpg", filename) is not None:
      predictImage(dirname+'/'+filename, True)

# check if the sunrise/sunset time file exists
# if so extract the sunrise and sunset times
def checkSunriseFile(filename):
  if path.isfile(filename)== False:
    return
  FH=open(filename, 'r')
  text = FH.readline()
  match = search("(\d+):(\d+)", text)
  if match is not None:
    times = text.split(':')
    newtime= datetime.combine(date.today(), time(int(times[0]), int(times[1])))+ \
      timedelta(minutes=-20)
    glbSunrise[0] = newtime.hour
    glbSunrise[1] = newtime.minute
    print "Sunrise set to "  + str(glbSunrise[0]) + ":" + str(glbSunrise[1])
  text = FH.readline()
  match = search("(\d+):(\d+)", text)
  if match is not None:
    times = text.split(':')
    newtime= datetime.combine(date.today(), time(int(times[0]), int(times[1])))+ \
      timedelta(minutes=30)
    glbSunset[0] = newtime.hour
    glbSunset[1] = newtime.minute
    print "Sunset set to "  + str(glbSunset[0]) + ":" + str(glbSunset[1])
  FH.close()
#
# predict the image 
# return True if closed
# return False if opened
# return the confidence
#   use the localtime() if filename does not fit yyyymmdd_hhmm_ss format
def predictImage(filename):
  dayTime = False
  match = search(r"(\d+)_(\d+)_(\d+)\.jpg", filename)
  checkSunriseFile(gDirectory + glbSunfile)

  if match is not None:
    dayTime = extract_localtime(match)[2]
  else:
    t = localtime()
    if (t.tm_hour*60+t.tm_min >= glbSunrise[0]*60+glbSunrise[1]) and \
      (t.tm_hour*60+t.tm_min <= glbSunset[0]*60+glbSunset[1]):
      dayTime=True

  if (dayTime==True):
    logger.info("Call dayPredict")
    confidence = dayPredict(filename)
  else:
    confidence = nightPredict(filename)

  closed = True
  if confidence < 0.5:
    closed = False
  return (closed, confidence)

# look at the files in a directory and process each file as open or closed
# foreach file {
#   if daytime, predict. if open, then move file to /open/. directory
#   if nighttime, Npredict, if open, then move file to /open/. directory }
def organize_pics(dirname):
  if path.exists(dirname)== False:
    print "directory does not exist"
    return
  open_dir = dirname+'/open'
  make_sure_path_exists(open_dir)
  filenames = listdir(dirname)
  for filename in filenames:
    # door is opened, move to directory
    if search(r"(.+)\.jpg", filename) is not None:
      if (predictImage(dirname+'/'+filename, False)[0]==False):
        move(dirname+'/'+filename, open_dir+'/'+filename)

def main():
  if len(sys.argv) == 2:
    filename = sys.argv[1]
    override = 'default'
  elif len(sys.argv) == 3:
    filename = sys.argv[1]
    override = sys.argv[2]
#  dayPredict(filename)
#  nightPredict(filename)
#  organize_pics(filename)
#  predict_pics(filename)

  if override == 'day':
    dayPredict(filename, True)
  elif override == 'night':
    nightPredict(filename, True)
  else:
    predictImage(filename, True)


if __name__ == '__main__':
  main()
