#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Time-stamp: <2013-04-08 16:19:30 vk>

import sys
import os
import re
import logging
import time
import datetime
from lib.orgformat import OrgFormat
from lib.memacs import Memacs
from lib.reader import CommonReader
from lib.orgproperty import OrgProperties
import pdb





class SimplePhoneLogsMemacs(Memacs):

    _REGEX_SEPARATOR = " *?# *?"

    ## match for example: "2012-11-20 # 19.59 # shutdown #   72 # 35682"
    ##                     0            1  2    3            4    5
    LOGFILEENTRY_REGEX = re.compile("([12]\d\d\d-[012345]\d-[012345]\d)" +
                                    _REGEX_SEPARATOR +
                                    "([ 012]\d)[:.]([012345]\d)" +
                                    _REGEX_SEPARATOR +
                                    "(.+)" +
                                    _REGEX_SEPARATOR +
                                    "(\d+)" +
                                    _REGEX_SEPARATOR +
                                    "(\d+)$")
    RE_ID_DATESTAMP = 0
    RE_ID_HOURS = 1
    RE_ID_MINUTES = 2
    RE_ID_NAME = 3
    RE_ID_BATT = 4
    RE_ID_UPTIME = 5

    phonelogfile_content = u""

    orgmode_result = u""

    def _parser_add_arguments(self):
        """
        overwritten method of class Memacs

        add additional arguments
        """
        Memacs._parser_add_arguments(self)

        self._parser.add_argument(
            "-f", "--file", dest="phonelogfile",
            action="store", required=True,
            help="path to sms xml backup file")


    def _parser_parse_args(self):
        """
        overwritten method of class Memacs

        all additional arguments are parsed in here
        """
        Memacs._parser_parse_args(self)
        if not (os.path.exists(self._args.phonelogfile) or \
                     os.access(self._args.phonelogfile, os.R_OK)):
            self._parser.error("input file not found or not readable")




    def _generateOrgentry(self, e_time, e_name, e_batt, e_uptime, e_last_opposite_occurrence, e_last_occurrence):
        """
        takes the data from the parameters and generates an Org-mode entry.

        @param e_time: time-stamp of the entry
        @param e_name: entry name/description
        @param e_batt: battery level
        @param e_uptime: uptime in seconds
        @param e_last_opposite_occurrence: time-stamp of previous opposite occurrence (if not False)
        @param e_last_occurrence: time-stamp of previous occurrence
        """

        #print "e_batt.__class__: [" + str(e_batt.__class__) + "]"

        assert e_time.__class__ == datetime.datetime
        assert e_name.__class__ == unicode
        assert e_batt.__class__ == str
        assert e_uptime.__class__ == str
        assert (e_last_opposite_occurrence.__class__ == datetime.datetime or not e_last_opposite_occurrence)
        assert (e_last_occurrence.__class__ == datetime.datetime or not e_last_occurrence)

        last_info = u''
        in_between = u''
        in_between_s = u''
        ignore_occurrence = False

        if e_last_opposite_occurrence:

            in_between_s = (e_time - e_last_opposite_occurrence).seconds + \
                (e_time - e_last_opposite_occurrence).days * 3600 * 24
            in_between = unicode(OrgFormat.get_hms_from_sec(in_between_s))

            if e_name == u'boot':
                last_info = u' (off for '
            elif e_name == u'shutdown':
                last_info = u' (on for '
            elif e_name.endswith(u'-end'):
                last_info = u' (' + e_name[0:-4].replace('wifi-','') + u' for '
            else:
                last_info = u' (not ' + e_name.replace('wifi-','') + u' for '
            last_info += unicode(OrgFormat.get_hms_from_sec(in_between_s)) + u')'

        if (e_name == u'boot') and \
                (e_last_occurrence and e_last_opposite_occurrence) and \
                (e_last_occurrence > e_last_opposite_occurrence):
            ## last boot is more recent than last shutdown -> crash has happened
            last_info = u' after crash'
            in_between = u''
            in_between_s = u''
            ignore_occurrence = True

        #pdb.set_trace()

            ## the programmer recommends you to read "memacs/tests/simplephonelogs_test.py"
            ## test_generateOrgentry_* for less cryptic examples on how this looks:
        return u'** ' + e_time.strftime('<%Y-%m-%d %a %H:%M>') + u' ' + e_name + last_info + \
            u'\n:PROPERTIES:\n:IN-BETWEEN: ' + in_between + \
            u'\n:IN-BETWEEN-S: ' + unicode(in_between_s) + \
            u'\n:BATT-LEVEL: ' + e_batt + \
            u'\n:UPTIME: ' + unicode(OrgFormat.get_hms_from_sec(int(e_uptime))) + \
            u'\n:UPTIME-S: ' + unicode(e_uptime) + u'\n:END:\n', ignore_occurrence


    def _determine_opposite_eventname(self, e_name):
        """
        Takes a look at the event and returns the name of the opposite event description.
        Opposite of 'boot' is 'shutdown' (and vice versa). 
        Opposite of 'foo' is 'foo-end' (and vice versa).

        @param e_name: string of an event name/description
        """

        assert (e_name.__class__ == unicode)

        if e_name == u'boot':
            return u'shutdown'
        elif e_name == u'shutdown':
            return u'boot'
        elif e_name.endswith(u'-end'):
            return e_name[0:-4]
        else:
            return e_name + u'-end'


    def _parse_data(self):
        """parses the phone log data"""

        last_occurrences = { } # holds the last occurrences of each event

        for rawline in self.phonelogfile_content.split('\n'):

            if not rawline:
                continue

            ## reset entry
            line = rawline.encode('utf-8')
            logging.debug("line: %s", line)

            components = re.match(self.LOGFILEENTRY_REGEX, line)

            if components:
                logging.debug("line matches")
            else:
                logging.debug("line does not match! (skipping this line)")
                continue

                ## extracting the components to easy to use variables:
            datestamp = components.groups()[self.RE_ID_DATESTAMP].strip()
            hours = int(components.groups()[self.RE_ID_HOURS].strip())
            minutes = int(components.groups()[self.RE_ID_MINUTES].strip())
            e_name = unicode(components.groups()[self.RE_ID_NAME].strip())
            e_batt = components.groups()[self.RE_ID_BATT].strip()
            e_uptime = components.groups()[self.RE_ID_UPTIME].strip()

            #pdb.set_trace()

            ## generating a datestamp object from the time information:
            e_time = datetime.datetime(int(datestamp.split('-')[0]),
                                       int(datestamp.split('-')[1]),
                                       int(datestamp.split('-')[2]),
                                       hours, minutes)

            opposite_e_name = self._determine_opposite_eventname(e_name)
            if opposite_e_name in last_occurrences:
                e_last_opposite_occurrence = last_occurrences[opposite_e_name]
            else:
                ## no previous occurrence of the opposite event type
                e_last_opposite_occurrence = False

            if e_name in last_occurrences:
                last_time = last_occurrences[e_name]
            else:
                last_time = False

            #pdb.set_trace()

            result, ignore_occurrence = self._generateOrgentry(e_time, e_name, e_batt, 
                                                               e_uptime, 
                                                               e_last_opposite_occurrence,
                                                               last_time)

            self.orgmode_result += result

            ## update last_occurrences-dict
            if not ignore_occurrence:
                last_occurrences[e_name] = e_time

            
##  ** <2012-11-20 Tue 11:56> boot (off for ?)
##  :PROPERTIES:
##  :IN-BETWEEN: -
##  :IN-BETWEEN-S: -
##  :BATT-LEVEL: 89
##  :UPTIME: 1:51:39
##  :UPTIME-S: 6692
##  :END:
## 
##  ** <2012-11-20 Tue 11:56> boot after crash
##  :PROPERTIES:
##  :IN-BETWEEN: -
##  :IN-BETWEEN-S: - 
##  :BATT-LEVEL: 89
##  :UPTIME: 1:51:34
##  :UPTIME-S: 6694
##  :END:
## 
##  ** <2012-11-20 Tue 19:59> shutdown (on for 9:54:42)
##  :PROPERTIES:
##  :IN-BETWEEN: 9:54:42
##  :IN-BETWEEN-S: 35682
##  :BATT-LEVEL: 72
##  :UPTIME: 9:54:42
##  :UPTIME-S: 35682
##  :END:
## 

    def _main(self):
        """
        gets called automatically from Memacs class.
        read the lines from phonecalls backup xml file,
        parse and write them to org file
        """

        self.phonelogfile_content = CommonReader.get_data_from_file(self._args.phonelogfile)

        self._parse_data()


# Local Variables:
# mode: flyspell
# eval: (ispell-change-dictionary "en_US")
# End:
