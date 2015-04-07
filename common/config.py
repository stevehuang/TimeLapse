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

import os
import re
import string
import inspect
import common.log as logging
import ConfigParser
import argparse
from types import *

logger = logging.getLogger()

def _handle_file_(x):
    if not os.path.isfile(x):
        return open(x, 'w')
    else:
        return open(x, 'rw')

# to use this module, please use
# from Parameters import *

class Opt (object):
    def __init__ (self, group='app', name=None, short=None, default=None, help=None, sub_group=''):
        self.group = group
        self.name = name
        self.short = short
        self.value = default
        self.help = help
        self.type = None
        self.sub_group = sub_group


    def add_opt_to_cli (self, parser):
        cli_name = self.name

        namelist = list()
        if (self.short is not None):
            namelist = [ "-" + self.short, "--" + cli_name]

        namelist.append("--" + cli_name)

        kwargs = { 'type' : self.type,
                   'help' : self.help,
                   'default': self._get_(),
                   'nargs': '?'
                 }
        if self.type == ListType:
            kwargs['type']=StringType
            kwargs['nargs']='+'
        if self.type == FileType:
            kwargs['type']=_handle_file_

        parser.add_argument(*namelist, **kwargs)


    def _get_ (self):
        return None

    def _set_ (self, value):
        if type(value) == self.type:
            self.value = value
        else:
            raise TypeError("Expected " + str(self.type))

class DirOpt(Opt):
    def __init__ (self, group='app', name=None, short=None, default=None, help=None, sub_group=''):
        default = os.path.expanduser(default) if default is not None else None
        default = os.path.expandvars(default) if default is not None else None
        #os.path.isdir(default)
        super(DirOpt,self).__init__(group, name, short, default, help, sub_group)
        self.type = StringType

    def _get_ (self):
        return self.value

class FileOpt(Opt):
    def __init__ (self, group='app', name=None, short=None, default=None, help=None, sub_group=''):
        default = os.path.expanduser(default) if default is not None else None
        default = os.path.expandvars(default) if default is not None else None
        super(FileOpt,self).__init__(group, name, short, default, help, sub_group)
        self.type = FileType

    def _get_ (self):
        if self.value is not None:
            if type(self.value) is FileType:
                return self.value.name
            else:
                return self.value
        return None

    def _set_ (self, value):
        try:
            super(FileOpt, self)._set_(value)
        except TypeError as e:
            if type(value) == StringType:
                self.value = FileType(value)
            else:
                raise TypeError("Expected " + str(self.type))

class IntOpt(Opt):
    def __init__ (self, group='app', name=None, short=None, default=None, help=None, sub_group=''):
        super(IntOpt,self).__init__(group, name, short, default, help, sub_group)
        self.type = IntType

    def _get_ (self):
        return self.value

class StrOpt(Opt):
    def __init__ (self, group='app', name=None, short=None, default=None, help=None, sub_group=''):
        super(StrOpt,self).__init__(group, name, short, default, help, sub_group)
        self.type = StringType

    def _get_ (self):
        return self.value

class ListOpt(Opt):
    def __init__ (self, group='app', name=None, short=None, default=None, help=None, sub_group=''):
        super(ListOpt,self).__init__(group, name, short, default, help, sub_group)
        self.type = ListType

    def _get_ (self):
        return self.value

class ConfigOptions:
    def __init__(self):
    # dictionary with (group,name) as the key
    # each item is an option (class Opt)
        self.groupOpts = dict()
        #self.args = list()
        self.parser = dict()
        self.parser['app'] = argparse.ArgumentParser(description='options for program', add_help=False)
        self.parser['app'].add_argument('-h', '--help', action='store_true', help='show this help message and exit', default=False)

    def __getattr__(self, name):
        for key, opt in self.groupOpts.iteritems():
            if name in key:
                return opt._get_()
        return None

    def _add_opts_to_cli_list_ (self):
        # create a parser cli list from the groupOpts list
        for key,opt in self.groupOpts.iteritems():
            opt.add_opt_to_cli(self.parser[key[0]])

    def _parse_config_files_ (self, filename):
        # parse
        ini_parser = ConfigParser.ConfigParser()
        ini_parser.read(filename)
        args = dict()
        for section in ini_parser.sections():
            items = ini_parser.items(section)
            for name, value in items:
                if not section in args:
                    args[section] = list()
                args[section].append('--' + name)
                args[section].extend(value.split())


        ini_parser = None
        return args

    def parseArgs (self, args=None, config_files=None, validate_values=False):
        # build a list of the cli options available from the current list

        # check if arg is config_file parameter. if so, break to the else
        # and parse the file. put the config parms into the self._args list
        # expand vars and user of all strings
        if len(args)==0:
            return None
        cli_args = dict()
        temp_args = list()
        self._add_opts_to_cli_list_() # fill in the parsers based on opts
        consume_conf = False
        for index, arg in enumerate(args):
            if arg == '--config_file' or arg.startswith('--config_file') or arg == '-c':
                consume_conf=True
                continue # consume the file conf argument

            if consume_conf==True and arg.endswith('.conf'):
                items = self._parse_config_files_(args[index])
                for groupname in items:
                    items[groupname] = [os.path.expanduser(x) for x in items[groupname]]
                    items[groupname] = [os.path.expandvars(x) for x in items[groupname]]
                    if not groupname in cli_args:
                        cli_args[groupname] = list()
                    cli_args[groupname].extend(items[groupname])
                consume_conf=False
            elif consume_conf==False:
                val = os.path.expanduser(args[index])
                val = os.path.expandvars(val)
                temp_args.append(val)
            else: # this means the conf file is not the right extension
                #print("Warning!!")
                logger.warning("Expected file with conf extension. File not parsed.")


        #  split the arguments into the groups
        group_found = False
        group_Name = 'app'
        for arg in temp_args:
            if arg=="--group" or arg.startswith('--group') or arg=='-g':
                group_found = True
                #print "group found"
                continue
            if group_found == True:
                group_Name = arg
                #print "group name set to " + group_Name
                group_found = False
                continue
            if not group_Name in cli_args:
                cli_args[group_Name] = list()
            cli_args[group_Name].append(arg)

        # parse all the parameters
        known_args = dict()
        unknown_args = dict()
        for groupname in self.parser:
            if groupname in cli_args:
                known, unknown = self.parser[groupname].parse_known_args(cli_args[groupname])
                if not groupname in known_args:
                    known_args[groupname] = known
                    unknown_args[groupname] = unknown
                else:
                    known_args[groupname].update(known)
                    unknown_args[groupname].update(unknown)

        # if help was called, print out
        if known_args['app'].help:
            for groupname in self.parser:
                self.parser[groupname].print_help()
            self.parser['app'].exit()

        #synch the namespace values with groupOpts
        for groupname in known_args:
            for name, value in vars(known_args[groupname]).iteritems():
                if self.groupOpts.has_key((groupname,name)):
                    self.groupOpts[(groupname,name)]._set_(value)
                else:
                    #print ("Missing key pair (%s, %s)" % (name,value))
                    if (name != 'help'):
                        logger.warning("Missing key pair (%s, %s)" % (name,value)) # 'help' will not be here. it's expected

        return known_args

    def _log_options_ (self):
        logger.debug('Dumping registered configuation options')
        for key, opt in self.groupOpts.iteritems():
            logger.debug("%s = %s" % (key, str(opt._get_())))

    def registerOpt (self, options=None):
        if (options is None):
            raise Exception('options is set to None')
        if (len(options)==0):
            raise Exception('nothing in options list')

        if type(options) is list:
            for opt in options:
                 # set the opt.module to the caller's __name__
                 #frm = inspect.stack()[1]
                 #mod = inspect.getmodule(frm[0])
                 #opt.module = mod.__module__
                 #logger.debug ("opt.module = %s" % mod)
                 # check if the opt.name in the group exists.
                groupname = opt.group
                if (groupname,opt.name) in self.groupOpts:
                    logger.warning("The name %s already exists. Option will be overwritten." % opt.name)
                    self.groupOpts[(groupname,opt.name)] = opt
                    if not (groupname in self.parser):
                        self.parser[groupname] = argparse.ArgumentParser(description='options for the group ' + groupname, add_help=False)
                else:
                    # the group does not exist. Add the first (key, item) pair
                    self.groupOpts[groupname, opt.name]=opt
                    if not (groupname in self.parser):
                        self.parser[groupname] = argparse.ArgumentParser(description='options for the group '+ groupname, add_help=False)
            #print self.groupOpts.items()

    def importOpt (self, module, name, group='app'):
        # check if the (group,name) pair exists in the dictionary
        __import__(module)
        if (group, name) in self.groupOpts:
            return self.groupOpts[(group, name)]._get_()
        else:
            raise ValueError("Missing pair (%s, %s) " % (group, name))
        return None

    def get_opt_list (self, group='app'):
        rval = []
        for key, opt in self.groupOpts.iteritems():
            if group in key:
                rval.append(key[1])
        return rval

Config = ConfigOptions()

