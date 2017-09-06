#!/usr/bin/env python
# Copyright 2017 Arthur Emerson, vreihen@yahoo.com
# Distributed under the terms of the GNU Public License (GPLv3)

from __future__ import with_statement
import math
import time
import weewx.units
import weedb
import weeutil.weeutil
import weewx.drivers
import weewx.wxformulas

import sys, getopt
from socket import *
import json
from collections import namedtuple
import datetime


# Default settings...
DRIVER_VERSION = "0.1"
HARDWARE_NAME = "WeatherFlow"
DRIVER_NAME = 'WeatherFlowUDP'
UDP_ADDRESS = '255.255.255.255'
UDP_PORT = 50222

def loader(config_dict, engine):
    return WeatherFlowUDPDriver(**config_dict[DRIVER_NAME])

# argv = sys.argv[1:]
# 
# # Parse command line options...
# try:
#    opts, args = getopt.getopt(argv,"hi:p:",["ip=","port=","help"])
# except getopt.GetoptError:
#    print sys.argv[0], '[--ip <listen_ip_address>] [--port <udp_port>] [-h]'
#    sys.exit(2)
# for opt, arg in opts:
#    if opt in ("-h", "--help"):
#       print sys.argv[0], '[--ip <listen_ip_address>] [--port <udp_port>] [-h]'
#       sys.exit()
#    elif opt in ("-i", "--ip"):
#       UDP_ADDRESS = arg
#    elif opt in ("-p", "--port"):
#       UDP_PORT = int(arg)
# print 'Listening for UDP broadcasts to IP address',UDP_ADDRESS,'on port',UDP_PORT,'...'

class WeatherFlowUDPDriver(weewx.drivers.AbstractDevice):

    def __init__(self, **stn_dict):
        last_obs_time_air = 0
        last_obs_time_sky = 0

    def hardware_name(self):
        return HARDWARE_NAME

    def genLoopPackets(self):
        last_obs_time_air = 0
        last_obs_time_sky = 0

        s = socket(AF_INET, SOCK_DGRAM)
        s.settimeout(None)
        s.bind((UDP_ADDRESS,UDP_PORT))

        while True:
            m = s.recvfrom(1024)
            # print m[0]
            x = json.loads(m[0], object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))

            if x.type == "obs_air":  # This is an Air barometer/temp/humidity/lightning packet
                # {"serial_number":"AR-00004424","type":"obs_air","obs":[[1502287861,1009.30,21.90,85,0,0,3.46,1]],"firmware_revision":17}
                #
                # Index  Field                          Units
                #   0    Time Epoch                     Seconds
                #   1    Station Pressure               MB
                #   2    Air Temperature                C
                #   3    Relative Humidity              %
                #   4    Lightning Strike Count
                #   5    Lightning Strike Avg Distance  km
                #   6    Battery                        V
                #   7    Report Interval                Minutes

                # print 'Air packet received!'
                # Air apparently sends two packets - last minute and current minute.  This if clause
                #   is a crude attempt to not send duplicate loop packets if we saw the
                #   last minute's packet already...
                if last_obs_time_air != x.obs[0][0]:
                    # print 'Latest packet!'
                    # _packet = {'dateTime': int(time.mktime(raw_time)),
                    _packet = {'dateTime': x.obs[0][0],
                        'usUnits' : weewx.METRIC,
                        'outTemp' : x.obs[0][2],
                        'outHumidity' : x.obs[0][3],
                        'pressure' : x.obs[0][1]
                        }
                    yield _packet
                    last_obs_time_air = x.obs[0][0]
                    
            if x.type == "obs_sky":  # This is a Sky wind/rain/solar packet
                #
                # Index  Field                          Units
                #   0    Time Epoch                     Seconds
                #   1    Lux
                #   2    UV                             Index 1-10
                #   3    Precip Accumulated
                #   4    Wind Lull                      mps
                #   5    Wind Avg                       mps
                #   6    Wind Gust                      mps
                #   7    Wind Direction                 Degrees
                #   8    Battery
                #   9    Report Interval                Minutes
                #  10    Solar Radiation

                # print 'Sky packet received!'
                # XYZ apparently sends two packets - last minute and current minute.  This if clause
                #   is a crude attempt to not send duplicate loop packets if we saw the
                #   last minute's packet already...
                if last_obs_time_sky != x.obs[0][0]:
                    # print 'Latest packet!'
                    # _packet = {'dateTime': int(time.mktime(raw_time)),
                    _packet = {'dateTime': x.obs[0][0],
                        # weewx.METRICWX = mm/mps ; weewx.METRIC = cm/kph
                        'usUnits' : weewx.METRICWX,
                        'windDir' : x.obs[0][7],
                        'windSpeed' : x.obs[0][5],
                        'windGust' : x.obs[0][6],
                        # Rain may need to be delta value since last loop packet?
                        'rain' : x.obs[0][3],
                        'UV' : x.obs[0][2],
                        'radiation' : x.obs[0][10]
                        }
                    yield _packet
                    last_obs_time_sky = x.obs[0][0]


# {"serial_number":"AR-00004424","type":"station_status","timestamp":1502287861,"uptime":10989664,"voltage":3.46,"version":17,"rssi":-62,"sensor_status":0}
# {"serial_number":"AR-00004424","type":"obs_air","obs":[[1502287861,1009.30,21.90,85,0,0,3.46,1]],"firmware_revision":17}
# {"serial_number":"HB-00001310","type":"hub-status","firmware_version":"13","uptime":105945,"rssi":-53,"timestamp":1502287902}

