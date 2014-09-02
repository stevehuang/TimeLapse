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
from scipy import optimize
import Image
import sys
import errno
from service import service

import scipy.optimize as optimize

Options = [
    Conf.StrOpt(name    = 'use',
                group   = 'trainer.Train_NN',
                default = 'classifier.train_NN:Train_NN.factory',
                help    = 'point to the neural network object used to train NN'),
    Conf.DirOpt (name    = 'path',
                 group   = 'trainer.Train_NN',
                 default = '$HOME/.garageeye/data',
                 help    = 'absolute path to image path'),
]

logger = logging.getLogger()
CONF = Conf.Config
CONF.registerOpt(Options)

input_layer_size = 320*220
hidden_layer_size = 50
output_layer_size  = 1

def sigmoid (x):
    y = 1.0 / (1.0 + numpy.exp(-1.0*x))
    return y

def sigmoidGradient (x):
    g = numpy.multiply(sigmoid(x), 1.0-sigmoid(x))
    return g

def add_bias_term (x, size, ax=1):
    ones_matrix = numpy.matrix(numpy.ones(size), dtype=numpy.float64)
    if ax == 1:
        ones_matrix = ones_matrix.T
    # 1x2
    # 50x2
    y = numpy.concatenate((ones_matrix, x), axis=ax)
    return y

def nnFeedForward (initial_theta, *args):
    inputX, Y = args
    border = hidden_layer_size*(input_layer_size+1)
    Theta1 = numpy.reshape(initial_theta[0:border], (hidden_layer_size, input_layer_size+1),order='F')
    Theta2 = numpy.reshape(initial_theta[border:], (output_layer_size, hidden_layer_size+1),order='F')
    m = inputX.shape[0]
    #feed forward network

    # input layer
    inputX = add_bias_term(inputX, m)
    z2 = Theta1*inputX.T
    a2 = sigmoid(z2)
    a2 = add_bias_term(a2, a2.shape[1], ax=0)

    # hidden layer
    z3 = Theta2*a2
    a3 = sigmoid(z3)
    a3 = a3.T

    # out
    J = numpy.multiply(-1.0*Y, numpy.log(a3)) - numpy.multiply(1.0-Y, numpy.log(1-a3))
    J = J.sum(axis=1)
    J = J.sum(axis=0)
    J = J / m
    return (J, z3, a3, z2, a2)

def nnGradCostFunction (initial_theta, *args):
    inputX, Y = args
    border = hidden_layer_size*(input_layer_size+1)
    Theta1 = numpy.reshape(initial_theta[0:border], (hidden_layer_size, input_layer_size+1), order='F')
    Theta2 = numpy.reshape(initial_theta[border:], (output_layer_size, hidden_layer_size+1),order='F')
    J, z3, a3, z2, a2 = nnFeedForward(initial_theta, *args)
    # use backpropagation algorithm to compute del(J) [gradient Cost]

    # m = samples
    # add 0s as extra term
    m = inputX.shape[0]

    # input layer
    inputX = add_bias_term(inputX, m)

    zeros_matrix = numpy.matrix(numpy.zeros(m), dtype=numpy.float64)
    z2 = numpy.concatenate((zeros_matrix, z2), axis=0)

    # initalize del terms
    Del2 = numpy.zeros((1, hidden_layer_size+1))
    Del1 = numpy.zeros((hidden_layer_size, input_layer_size+1))
    for sample in range(m):
        h = a3[sample, :].T
        y_sample = Y[sample,:].T
        delta3 = h - y_sample
        delta2 = numpy.multiply( Theta2.T*delta3, sigmoidGradient(z2[:, sample]) )
        delta2 = delta2[1:]
        Del2 = Del2 + delta3*a2[:, sample].T
        Del1 = Del1 + delta2*inputX[sample,:]

    # no lambda tern for now. This means no regularization
    gradTheta2 = Del2 / m
    gradTheta1 = Del1 / m
    return (numpy.concatenate(((gradTheta1.T).ravel(), (gradTheta2.T).ravel()), axis=1).T).A1

def nnCostFunction (initial_theta, *args):
    J, z3, a3, z2, a2 = nnFeedForward(initial_theta, *args)
    return J.A1

# class that runs a Neural Network
class Train_NN (service.Service):

    def __init__(self, path):
        super(Train_NN, self).__init__()
        self.img_path = path
        logger.debug("Img_path = " + str(self.img_path))
        self.args = None

    def start(self):
        """
            service.Services.run_service will call this to start the service.
            This function will add a periodic_timer call to tg (thread groups).
            add_periodic_timer spawns a new gt which will be run at a certain
            time interval
        """
        logger.info("started Training process")
        self.train_set()
        logger.info("ending Training process")

    def stop(self):
        pass


    def train_set (self):
        #img_path = CONF.importOpt(module='classifier.train_NN', name='path', group='trainer.Train_NN')
        opened_path = path.join(self.img_path, "TrainingSet/day/opened")
        closed_path = path.join(self.img_path, "TrainingSet/day/closed")

        files_list = list()
        results_list = list()
        # get each file in path. Add jpg to the list
        for file in listdir(closed_path) :
            if search(r"(.+)\.jpg", file) is not None:
                files_list.append(os.path.join(closed_path,file))
                results_list.append(1)
        for file in listdir(opened_path) :
            if search(r"(.+)\.jpg", file) is not None:
                files_list.append(os.path.join(opened_path,file))
                results_list.append(0)
        self.train(files_list, results_list)

    # load jpeg image and convert to greyscale
    def load_image (self, filename):
        im = Image.open(filename).convert("L")
        im = im.resize( (320, 240) )
        im = im.crop( (0,0, 320, 220) )
        return im

    # create a matrix with random values of the size input_layer_size by output_layer_size
    def randInitializeWeights (self,in_size, out_size):
        # zeros = [ [0 for col in range(input_layer_size+1)] for row in range(output_layer_size)]
        A = numpy.random.random((in_size+1, out_size))
        logger.debug("randInitializeWeight zero matrix produced of dimension " + str(A.shape))
        InitEpsilon = 0.12
        return (A*(2*InitEpsilon) - InitEpsilon)

    def predict(self, Theta1, Theta2, X):
        m = X.shape[0]
        num_labels = Theta2.shape[0]
        onesMat = numpy.ones( (m, 1), dtype=numpy.float64 )
        h1 = sigmoid(numpy.dot (numpy.hstack((onesMat, X)), Theta1.T))
        h2 = sigmoid(numpy.dot (numpy.hstack((onesMat, h1)), Theta2.T))
        return h2

    def callbackIterationDone (self, xk):
        print "Iteration completed"
        x,y = self.args
        J = nnCostFunction(xk, x,y)
        print "Cost J is " + str(J)

    # Input a list of images, list of their states [closed/open]
    # note, image size is 320*220
    def train (self, image_files, results):
        logger.info("training - BEGIN")
        # image_files is filenames of images
        # results is 1 and 0s
        imageArr = list()
        imageMatrix = None
        resultsMatrix=None

        # extract the files and create a matrix where
        # each row belongs to the image (e.g. jpg)
        # and the elements (cols) are the image data
        for filename in image_files:
            imageX = numpy.matrix(self.load_image(filename), dtype=numpy.float64)
            imageX = imageX.flatten('F')
            if imageMatrix is None:
                imageMatrix = numpy.matrix(imageX, dtype=numpy.float64)
            else:
                imageMatrix = numpy.concatenate((imageMatrix, imageX))
        resultsMatrix = numpy.matrix(results, dtype=numpy.float64).T



        # print out debug data
        logger.debug("Input Matrix dimension: " + str(imageMatrix.shape))
        logger.debug("Results Matrix dimension: " + str(resultsMatrix.shape))
        Theta1 = self.randInitializeWeights (input_layer_size, hidden_layer_size).T
        Theta2 = self.randInitializeWeights (hidden_layer_size, output_layer_size).T
        logger.debug("Theta_1 Matrix dimension: " + str(Theta1.shape))
        logger.debug("Theta_2 Matrix dimension: " + str(Theta2.shape))

        # unroll the initial NN parameters into an array
        initial_nn_parameters = numpy.concatenate((Theta1.flatten('F'), Theta2.flatten('F')))

        self.args = (imageMatrix, resultsMatrix)
        thetas = optimize.fmin_cg(nnCostFunction, initial_nn_parameters, fprime=nnGradCostFunction, args=self.args, maxiter=5, callback=self.callbackIterationDone)
        #thetas = initial_nn_parameters
        # roll the theta together
        border = hidden_layer_size*(input_layer_size+1)
        _Theta1_ = numpy.reshape(thetas[0:border], (hidden_layer_size, input_layer_size+1), order='F')
        _Theta2_ = numpy.reshape(thetas[border:], (output_layer_size, hidden_layer_size+1), order='F')
        y = self.predict(_Theta1_, _Theta2_, imageMatrix)
        accuracy = numpy.mean((y>0.5)==resultsMatrix)
        logger.debug("Accuracy is about " + str(accuracy))
        logger.info("Training NN completed")

    @staticmethod
    def factory (conf_vars):
        return Train_NN(conf_vars['path'])

