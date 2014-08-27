import common.log as logging
import common.config as Conf
import os, sys, signal, errno
import predict

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


Options = [
    Conf.StrOpt(name    = 'use',
                group   = 'classifier.Predicter_NN',
                default = 'classifier.predict_NN:Predicter_NN.factory',
                help    = 'point to the neural network object used to predict results'),
    Conf.FileOpt(name    = 'mat_file',
                 group   = 'classifier.Predicter_NN',
                 default = '$HOME/.garageeye/default.mat',
                 help    = 'absolute path to mat file format including the filename'),
    Conf.FileOpt(name    = 'nmat_file',
                 group   = 'classifier.Predicter_NN',
                 default = '$HOME/.garageeye/default.mat',
                 help    = 'absolute path to mat file format including the filename'),

]

logger = logging.getLogger()
CONF = Conf.Config
CONF.registerOpt(Options)


# sigmoid function
def sigmoid(z):
  onesMatrix = numpy.ones( z.shape )
  simplefilter("ignore", RuntimeWarning)
  rval = numpy.exp(-z)
  simplefilter("default", RuntimeWarning)
  rval = onesMatrix / (onesMatrix + rval)
  return rval

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


class Predicter_NN (predict.Predicter):
    def __init__(self, mat_file, nmat_file):
        super(Predicter_NN, self).__init__()
        self.mat_file = mat_file
        self.nmat_file = nmat_file

    def load_image (self, filename):
        im = Image.open(filename).convert("L")
        im = im.resize( (320, 240) )
        im = im.crop( (0,0, 320, 220) )
        return im

    def dayPredict(self, filename):
        imageX = numpy.matrix(self.load_image(filename), \
             dtype=numpy.float64)
        imageX = imageX.flatten('F')

        try:
            x=io.loadmat(self.mat_file, None, False)
        except:
            logger.error("Load mat failed")
            return 0

        Theta1 = x['Theta1']
        Theta2 = x['Theta2']
        confidence = self.calculateSigmoid(Theta1, Theta2, imageX)
        if (confidence[0,0] > 0.5):
            logger.debug(filename + "\t(" + str(confidence[0,0]) + ") \t[closed]")
        if (confidence[0,0] <= 0.5):
            logger.debug(filename + "\t(" + str(confidence[0,0]) + ") \t[opened]")
        return confidence

    def nightPredict(self, filename):
        imageX = numpy.matrix(self.load_image(filename), \
                              dtype=numpy.float64)

        # it's really really dark.
        if (numpy.std(imageX.flatten('F')) < 1.0):
            logger.debug(filename + "\t(0.99999999)\t[closed]")
            return 0.999

        imageX = histeq(imageX)
        imageX = imageX.flatten('F')

        try:
            x=io.loadmat(self.nmat_file, None, False)
        except:
            logger.error("Load mat failed")
            return 0

        Theta1 = x['Theta1']
        Theta2 = x['Theta2']
        confidence = self.calculateSigmoid(Theta1, Theta2, imageX)
        if (confidence[0,0] > 0.5):
            logger.debug(filename + "\t(" + str(confidence[0,0]) + ") \t[closed]")
        if (confidence[0,0] <= 0.5):
            logger.debug(filename + "\t(" + str(confidence[0,0]) + ") \t[opened]")
        return confidence

    # 3 layer NN
    # 320x240 array input layer
    # 50 node hidden layer
    # 1 output layer
    def calculateSigmoid(self, Theta1, Theta2, X):
        m = X.shape[0]
        num_labels = Theta2.shape[0]
        onesMat = numpy.ones( (m, 1), dtype=numpy.float64 )
        h1 = sigmoid(numpy.dot (numpy.hstack((onesMat, X)), Theta1.T))
        h2 = sigmoid(numpy.dot (numpy.hstack((onesMat, h1)), Theta2.T))
        return h2

    def predictImage (self, filename):
        dayTime = True
        if (dayTime==True):
            confidence = self.dayPredict(filename)
        else:
            confidence = self.nightPredict(filename)

        closed = True
        if confidence < 0.5:
            closed = False

        return (closed, confidence)

    def predict(self, filename):
        logger.debug("predicter_NN called")
        self.predictImage(filename)

    @staticmethod
    def factory (conf_vars):
        return Predicter_NN(conf_vars['mat_file'], conf_vars['nmat_file'])

