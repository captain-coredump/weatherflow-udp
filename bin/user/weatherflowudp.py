#!/usr/bin/env python
# Copyright 2017 Arthur Emerson, vreihen@yahoo.com
# Distributed under the terms of the GNU Public License (GPLv3)

"""
This driver detects different sensors packets broadcast using the WeatherFlow
UDP JSON protocol, and it includes a mechanism to filter the incoming data
and map the filtered data onto the weewx database schema and identify the
type of data from each sensor.

Sensors are filtered based on a tuple that identifies uniquely each sensor.
A tuple consists of the observation name, a unique identifier for the hardware,
and the packet type, separated by periods:

  <observation_name>.<hardware_id>.<packet_type>

The filter and data types are specified in a sensor_map stanza in the driver
stanza.  For example:

[WeatherFlowUDP]
    driver = user.weatherflowudp
    [[sensor_map]]
        outTemp = temperature.AR-00004424.obs_air
        rain = rain.SK-00001234.obs_sky

If no sensor_map is specified, no data will be collected.

To identify sensors, run the driver directly.  Alternatively, use the options
log_unknown_sensors and log_unmapped_sensors to see data from the local
network that are not yet recognized by your configuration.

[WeatherFlowUDP]
    driver = user.weatherflowudp

The default for each of these is False.

"""

from __future__ import with_statement
import math
import time
import weewx.units
import weedb
import weeutil.weeutil
import weewx.drivers
import weewx.wxformulas
# from weeutil.weeutil import tobool
import syslog

import sys, getopt
from socket import *
import json
from collections import namedtuple
import datetime


# Default settings...
DRIVER_VERSION = "0.3"
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

    # map the counter total to the counter delta.  for example, the pair
    #   rain:rainTotal
    # will result in a delta called 'rain' from the cumulative 'rainTotal'.
    # these are applied to mapped packets.
    #DEFAULT_DELTAS = {
    #    'rain': 'rainTotal',
    #    'strikes': 'strikes_total'}

    def __init__(self, **stn_dict):
        last_obs_time_air = 0
        last_obs_time_sky = 0
        last_obs_rapid_wind = 0
        last_obs_rain = 0
        # loginf('driver version is %s' % DRIVER_VERSION)
        self._sensor_map = stn_dict.get('sensor_map', {})
        # loginf('sensor map is %s' % self._sensor_map)
        ## print 'sensor map is ', self._sensor_map
        ## sensor map is  {'outTemp': 'temperature.AR-00004424.obs_air', 'outHumidity': 'humidity.AR-00004424.obs_air'}
        #self._deltas = stn_dict.get('deltas', WeatherFlowUDPDriver.DEFAULT_DELTAS)
        # loginf('deltas is %s' % self._deltas)

    def hardware_name(self):
        return HARDWARE_NAME

    def genLoopPackets(self):
        last_obs_time_air = 0
        last_obs_time_sky = 0
        last_obs_rapid_wind = 0
        last_obs_rain = 0

        udp_socket = socket(AF_INET, SOCK_DGRAM)
        udp_socket.settimeout(None)
        udp_socket.bind((UDP_ADDRESS,UDP_PORT))

        while True:
            udp_raw = udp_socket.recvfrom(1024)
            # print udp_packet[0]
            udp_packet = json.loads(udp_raw[0], object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))

            # print udp_packet


            if udp_packet.type == "obs_air":  # This is an Air barometer/temp/humidity/lightning packet
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
                if last_obs_time_air != udp_packet.obs[0][0]:
                    # print 'Latest packet!'
                    # _packet = {'dateTime': int(time.mktime(raw_time)),
                    _packet = {'dateTime': udp_packet.obs[0][0],
                        'usUnits' : weewx.METRIC,
                        'outTemp' : udp_packet.obs[0][2],
                        'outHumidity' : udp_packet.obs[0][3],
                        'pressure' : udp_packet.obs[0][1]
                        }
                    yield _packet
                    last_obs_time_air = udp_packet.obs[0][0]
                    
            if udp_packet.type == "obs_sky":  # This is a Sky wind/rain/solar packet
                # {"serial_number":"SK-00001234","type":"obs_sky","hub_sn":"HB-00001357","obs":[[1509404073,null,0,0.000,0.09,0.50,0.94,230,3.37,1,0]],"firmware_revision":27}
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
                if last_obs_time_sky != udp_packet.obs[0][0]:
                    # print 'Latest packet!'
                    # _packet = {'dateTime': int(time.mktime(raw_time)),
                    _packet = {'dateTime': udp_packet.obs[0][0],
                        # weewx.METRICWX = mm/mps ; weewx.METRIC = cm/kph
                        'usUnits' : weewx.METRICWX,
                        'windDir' : udp_packet.obs[0][7],
                        'windSpeed' : udp_packet.obs[0][5],
                        'windGust' : udp_packet.obs[0][6],
                        # Rain may need to be delta value since last loop packet?
                        #'rainTotal' : udp_packet.obs[0][3],
                        'rain' : udp_packet.obs[0][3],
                        #'rain' : udp_packet.obs[0][3] - last_obs_rain,
                        'UV' : udp_packet.obs[0][2],
                        'radiation' : udp_packet.obs[0][10]
                        }
                    yield _packet
                    last_obs_time_sky = udp_packet.obs[0][0]
                    last_obs_rain = udp_packet.obs[0][3]


            if udp_packet.type == "rapid_wind":  # This is a Sky near-realtime wind packet (sent rapidly, not just once per minute)
                # {"serial_number":"SK-00001234","type":"rapid_wind","hub_sn":"HB-00001357","ob":[1509408513,1.07,159]}
                #
                # Index  Field                          Units
                #   0    Time Epoch                     Seconds
                #   1    Wind Speed (instantaneous?)    mps
                #   2    Wind Direction                 Degrees

                # SKY apparently sends two packets - last minute and current minute.  This if clause
                #   is a crude attempt to not send duplicate loop packets if we saw the
                #   last minute's packet already...
                if last_obs_rapid_wind != udp_packet.ob[0]:
                    # print 'Latest packet!'
                    # _packet = {'dateTime': int(time.mktime(raw_time)),
                    _packet = {'dateTime': udp_packet.ob[0],
                        # weewx.METRICWX = mm/mps ; weewx.METRIC = cm/kph
                        'usUnits' : weewx.METRICWX,
                        'windSpeed' : udp_packet.ob[1],
                        'windDir' : udp_packet.ob[2]
                        }
                    yield _packet
                    last_obs_rapid_wind = udp_packet.ob[0]

                    

# {"serial_number":"AR-00004424","type":"station_status","timestamp":1502287861,"uptime":10989664,"voltage":3.46,"version":17,"rssi":-62,"sensor_status":0}
# {"serial_number":"AR-00004424","type":"obs_air","obs":[[1502287861,1009.30,21.90,85,0,0,3.46,1]],"firmware_revision":17}
# {"serial_number":"HB-00001357","type":"hub-status","firmware_version":"13","uptime":105945,"rssi":-53,"timestamp":1502287902}
# {"serial_number":"SK-00001234","type":"station_status","hub_sn":"HB-00001357","timestamp":1509404073,"uptime":2532,"voltage":3.37,"version":27,"rssi":-41,"sensor_status":0}
# {"serial_number":"SK-00001234","type":"obs_sky","hub_sn":"HB-00001357","obs":[[1509404073,null,0,0.000,0.09,0.50,0.94,230,3.37,1,0]],"firmware_revision":27}
# {"serial_number":"SK-00001234","type":"rapid_wind","hub_sn":"HB-00001357","ob":[1509408513,1.07,159]}
# {"serial_number":"SK-00001234","type":"light_debug","hub_sn":"HB-00001357","ob":[1509408516,0,0,1,0]}
# {"serial_number":"SK-00001234","type":"wind_debug","hub_sn":"HB-00001357","ob":[1509408516,40,212,0,0,1655,1628,1767,1775,1733,1737,1793,1814]}
