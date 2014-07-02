# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
# Copyright 2014 Steve Huang
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Author: Steve Huang (huangwSteve@hotmail.com)
Initial Date: July 2014
Module Description:

  TBD
"""

import sys
import logging
import logging.handlers

DEFAULT_LOGGER_NAME='garage_eye'

def getLogger(name=DEFAULT_LOGGER_NAME):
    logger = logging.getLogger(name)
    return logger
  
def getLevelName(level):
    return logging.getLevelName(level)

def setup (name=None,level='INFO', conf_file=None):
    logger=None
    if (name is None):
        logger = getLogger()
    else:
        logger = getLogger(name)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.getLevelName(level))
    formatter = logging.Formatter('[%(asctime)s] %(module)s-%(funcName)s:%(lineno)d: %(message)s', "%H:%M:%S")
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger.setLevel(logging.getLevelName(level))

    if (conf_file is not None):
        filelog = logging.handlers.RotatingFileHandler(conf_file, maxBytes=104857600, backupCount=10)
        filelog.setFormatter(formatter)
        logger.addHandler(filelog)
    return logger
