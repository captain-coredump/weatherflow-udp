#!/usr/bin/env python
# Copyright 2017-2020 Arthur Emerson, vreihen@yahoo.com
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
stanza.  For example, on an Air/Sky setup:

[WeatherFlowUDP]
    driver = user.weatherflowudp
    log_raw_packets = False
    udp_address = <broadcast>
    # udp_address = 0.0.0.0
    # udp_address = 255.255.255.255
    udp_port = 50222
    udp_timeout = 90
    share_socket = True

    [[sensor_map]]
        outTemp = air_temperature.AR-00004424.obs_air
        outHumidity = relative_humidity.AR-00004424.obs_air
        pressure =  station_pressure.AR-00004424.obs_air
        # lightning_strikes =  lightning_strike_count.AR-00004424.obs_air
        # avg_distance =  lightning_strike_avg_distance.AR-00004424.obs_air
        outTempBatteryStatus =  battery.AR-00004424.obs_air
        windSpeed = wind_speed.SK-00001234.rapid_wind
        windDir = wind_direction.SK-00001234.rapid_wind
        # lux = illuminance.SK-00001234.obs_sky
        UV = uv.SK-00001234.obs_sky
        rain = rain_accumulated.SK-00001234.obs_sky
        windBatteryStatus = battery.SK-00001234.obs_sky
        radiation = solar_radiation.SK-00001234.obs_sky
        # lightningYYY = distance.AR-00004424.evt_strike
        # lightningZZZ = energy.AR-00004424.evt_strike

*** If no sensor_map is specified, no data will be collected. ***

For a sample Tempest sensor_map, see the file sample_Tempest_sensor_map on GitHub:

https://github.com/captain-coredump/weatherflow-udp/blob/master/sample_Tempest_sensor_map

To identify sensors, use the option 'log_raw_packets = True' to
output all raw received packets into syslog where you can examine
what is being sent.  Make sure to set 'log_raw_packets = False'
when done, since it will generate a LOT of syslog entries over
time.

To identify the various observation_name options, start weewx
with this station driver installed and it will write the
entire matrix of available observation_names and sensor_types
to syslog or wherever weewx is configured to send log info.

Apologies for the long observation_names, but I figured that
it would be best if I used the documented field names from
WeatherFlow's UDP packet specs (v37 at the time of writing) 
with underscores between words so that the names were
consistent with their protocol documentation.  See
https://weatherflow.github.io/SmartWeather/api/udp.html

Options:

    log_raw_packets = False

    Enable writing all raw UDP packets received to syslog,
    or wherever weewx is configured to send log info.  Will
    fill up your logs pretty quickly, so only use it as
    a debugging tool or to identify sensors.

    udp_address = <broadcast>
    # udp_address = 0.0.0.0
    # udp_address = 255.255.255.255

    This is the broadcast address that we should be listening
    on for packets.  If the driver throws an error on start,
    try one of the other commented-out options (in order).
    This seems to be platform-specific.  All three work on
    Debian Linux and my Raspberry Pi, but only 0.0.0.0 works
    on my Macbook running OS-X or MacOS.  Don't ask about
    Windows, since I don't have a test platform to see
    if it will even work.

    udp_port = 50222

    The IP port that we should be listening for UDP packets
    from.  WeatherFlow's default is 50222.

    udp_timeout = 90

    The number of seconds that we should wait for an incoming
    packet on the UDP socket before we give up and log an
    error into syslog.  I cannot determine whether or not
    weewx cares whether a station driver is non-blocking or
    blocking, but encountered a situation in testing where
    the WeatherFlow Hub rebooted for a firmware update and
    it caused the driver to throw a timeout error and exit.
    I have no idea what the default timeout value even is, but
    decided to make it configurable in case it is important
    to someone else.  My default of 90 seconds seems reasonable,
    with the Air sending observations every 60 seconds.  If
    you are an old-school programmer like me who thinks that
    computers should wait forever until they receive data,
    the Python value "None" should disable the timeout.  In
    any case, the driver will just log an error into syslog
    and keep on processing.  It isn't like it is the end
    of the world if you pick a wrong value, but you may have
    a better chance of missing packets during the brief error
    trapping time with a really short duration.

    share_socket = False

    Whether or not the UDP socket should be shared with other
    local programs also listening for WeatherFlow packets.  Default
    is False because I suspect that some obscure Python implementation
    will have problems sharing the socket.  Feel free to set it to
    True if you have other apps running on your weewx host listening
    for WF UDP packets.

Finally, let me add a thank you to Matthew Wall for the
sensor map naming logic that I borrowed from his weewx-SDR
station driver code: 

https://github.com/matthewwall/weewx-sdr

I guess that I should also thank David St. John and the
"dream team" at WeatherFlow for all of the hard work and
forethought that they put into making this weather station
a reality.  I can't sing enough praises for whoever came
up with the idea to send observation packets out live via
UDP broadcasts, and think that they should be nominated
for a Nobel Prize or something...

"""

from __future__ import with_statement
import math
import time
import weewx.units
import weedb
import weeutil.weeutil
import weewx.drivers
import weewx.wxformulas
from weeutil.weeutil import tobool
import syslog
import threading

import sys, getopt
from socket import *
import json
from collections import namedtuple
import datetime

# Default settings...
DRIVER_VERSION = "1.10"
HARDWARE_NAME = "WeatherFlow"
DRIVER_NAME = 'WeatherFlowUDP'

# Observation record fields...
fields = dict()
fields['obs_air'] = ('time_epoch', 'station_pressure', 'air_temperature', 'relative_humidity', 'lightning_strike_count', 'lightning_strike_avg_distance', 'battery', 'report_interval')
fields['obs_sky'] = ('time_epoch', 'illuminance', 'uv', 'rain_accumulated', 'wind_lull', 'wind_avg', 'wind_gust', 'wind_direction', 'battery', 'report_interval', 'solar_radiation', 'local_day_rain_accumulation', 'precipitation_type', 'wind_sample_interval')
fields['rapid_wind'] = ('time_epoch', 'wind_speed', 'wind_direction')
fields['evt_precip'] = ('time_epoch')
fields['evt_strike'] = ('time_epoch', 'distance', 'energy')
fields['obs_st'] = ('time_epoch', 'wind_lull', 'wind_avg', 'wind_gust', 'wind_direction', 'wind_sample_interval', 'station_pressure', 'air_temperature', 'relative_humidity', 'illuminance', 'uv', 'solar_radiation', 'rain_accumulated', 'precipitation_type', 'lightning_strike_avg_distance', 'lightning_strike_count', 'battery', 'report_interval')

def loader(config_dict, engine):
    return WeatherFlowUDPDriver(**config_dict[DRIVER_NAME])

def logmsg(level, msg):
    syslog.syslog(level, 'weatherflowudp: %s: %s' %
                  (threading.currentThread().getName(), msg))

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def sendMyLoopPacket(pkt,sensor_map):
    packet = dict()
    if 'time_epoch' in pkt:
        packet = {'dateTime': pkt['time_epoch'],
            # weewx.METRICWX = mm/mps ; weewx.METRIC = cm/kph
            'usUnits' : weewx.METRICWX}

    #for pkt_weewx, pkt_label in sensor_map.iteritems():     # Python 2
    for pkt_weewx, pkt_label in list(sensor_map.items()):    # Python 3
        if pkt_label.replace("-","_") in pkt:
           packet[pkt_weewx] = pkt[pkt_label.replace("-","_")]

    return packet

def parseUDPPacket(pkt):
    packet = dict()
    if 'serial_number' in pkt:
        if 'type' in pkt:
            serial_number = pkt['serial_number'].replace("-","_")
            pkt_type = pkt['type']
            pkt_label = serial_number + "." + pkt_type
            #pkt_keys = pkt.keys()         # Python 2
            pkt_keys = list(pkt.keys())    # Python 3
            for i in pkt_keys:
                pkt_item = i + "." + pkt_label
                packet[pkt_item] = pkt[i]

            if pkt_type == 'obs_air':
                packet['time_epoch'] = pkt['obs'][0][0]
                for i1, obs_val in enumerate(pkt['obs'][0]):
                    pkt_item1 =  fields['obs_air'][i1] + "." + pkt_label
                    packet[pkt_item1] = obs_val

            if pkt_type == 'obs_sky':
                packet['time_epoch'] = pkt['obs'][0][0]
                for i1, obs_val in enumerate(pkt['obs'][0]):
                    pkt_item1 =  fields['obs_sky'][i1] + "." + pkt_label
                    packet[pkt_item1] = obs_val

            if pkt_type == 'obs_st':
                packet['time_epoch'] = pkt['obs'][0][0]
                for i1, obs_val in enumerate(pkt['obs'][0]):
                    pkt_item1 =  fields['obs_st'][i1] + "." + pkt_label
                    packet[pkt_item1] = obs_val

            if pkt_type == 'rapid_wind':
                packet['time_epoch'] = pkt['ob'][0]
                for i1, obs_val in enumerate(pkt['ob']):
                    pkt_item1 =  fields['rapid_wind'][i1] + "." + pkt_label
                    packet[pkt_item1] = obs_val

            if pkt_type == 'evt_strike':
                packet['time_epoch'] = pkt['evt'][0]
                for i1, obs_val in enumerate(pkt['evt']):
                    pkt_item1 =  fields['evt_strike'][i1] + "." + pkt_label
                    packet[pkt_item1] = obs_val

            if pkt_type == 'evt_precip':
                packet['time_epoch'] = pkt['evt'][0]
                for i1, obs_val in enumerate(pkt['evt']):
                    pkt_item1 =  fields['evt_precip'][i1] + "." + pkt_label
                    packet[pkt_item1] = obs_val

            if pkt_type == 'device_status':
                packet['time_epoch'] = pkt['timestamp']

            if pkt_type == 'hub_status':
                packet['time_epoch'] = pkt['timestamp']

            if pkt_type[0:2] == 'X_':
                packet['time_epoch'] = int(time.time())

        else:
            loginf('Corrupt UDP packet? %s' % pkt)
    else:
        loginf('Corrupt UDP packet? %s' % pkt)
    return packet


class WeatherFlowUDPDriver(weewx.drivers.AbstractDevice):

    def __init__(self, **stn_dict):
        loginf('driver version is %s' % DRIVER_VERSION)
        self._log_raw_packets = tobool(stn_dict.get('log_raw_packets', False))
        self._udp_address = stn_dict.get('udp_address', '<broadcast>')
        self._udp_port = int(stn_dict.get('udp_port', 50222))
        self._udp_timeout = int(stn_dict.get('udp_timeout', 90))
        self._share_socket = tobool(stn_dict.get('share_socket', False))
        self._sensor_map = stn_dict.get('sensor_map', {})
        loginf('sensor map is %s' % self._sensor_map)
        loginf('*** Sensor names per packet type')
        #for pkt_type in fields.keys():                  # Python 2
        for pkt_type in list(fields.keys()):             # Python 3
            loginf('packet %s: %s' % (pkt_type,fields[pkt_type]))

    @property
    def hardware_name(self):
        return HARDWARE_NAME


    def genLoopPackets(self):
        loginf('Listening for UDP broadcasts to IP address %s on port %s, with timeout %s and share_socket %s...' % (self._udp_address,self._udp_port,self._udp_timeout,self._share_socket))

        s=socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        if self._share_socket == True:
            s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        s.bind((self._udp_address,self._udp_port))
        s.settimeout(self._udp_timeout)

        while True:
            timeouterr=0
            try:
                m=s.recvfrom(1024)
            except timeout:
                timeouterr=1
                logerr('Socket timeout waiting for incoming UDP packet!')
            if timeouterr == 0:
                try:
                    m0 = str(m[0],'utf-8').replace(",null",",None")    # Python 3
                except:
                    m0 = m[0].replace(",null",",None")                 # Python 2
                m1=''
                try:
                    m1=eval(m0)
                except SyntaxError:
                    logerr('Packet parse error: %s' % m0)
                if self._log_raw_packets:
                    loginf('raw packet: %s' % m1)
                m2=parseUDPPacket(m1)
                m3=sendMyLoopPacket(m2, self._sensor_map)
                if len(m3) > 2:
                    yield m3


