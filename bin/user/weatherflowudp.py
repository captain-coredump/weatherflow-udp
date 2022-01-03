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

To identify sensors, run the driver directly. For help on the various options, try
  cd /home/weewx
  PYTHONPATH=/home/weewx/bin python ./bin/user/weatherflowudp.py --help

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
import json
import time

import sys
from socket import *

import weewx.units
import weewx.drivers
import weewx.wxformulas
import weewx.accum
from weeutil.weeutil import tobool
import requests
from datetime import datetime
import calendar
from configobj import ConfigObj

# Default settings...
DRIVER_VERSION = "1.13"
HARDWARE_NAME = "WeatherFlow"
DRIVER_NAME = 'WeatherFlowUDP'

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging

    log = logging.getLogger(__name__)


    def logdbg(msg):
        log.debug(msg)


    def loginf(msg):
        log.info(msg)


    def logwrn(msg):
        log.warning(msg)


    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog


    def logmsg(level, msg):
        syslog.syslog(level, 'weatherflowudp: %s:' % msg)


    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)


    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)


    def logwrn(msg):
        logmsg(syslog.LOG_WARNING, msg)


    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)

class DriverException(Exception):
    pass

# Observation record fields...
fields = dict()
fields['obs_air'] = ('time_epoch', 'station_pressure', 'air_temperature', 'relative_humidity', 'lightning_strike_count', 'lightning_strike_avg_distance', 'battery', 'report_interval')
fields['obs_sky'] = ('time_epoch', 'illuminance', 'uv', 'rain_accumulated', 'wind_lull', 'wind_avg', 'wind_gust', 'wind_direction', 'battery', 'report_interval', 'solar_radiation', 'local_day_rain_accumulation', 'precipitation_type', 'wind_sample_interval')
fields['rapid_wind'] = ('time_epoch', 'wind_speed', 'wind_direction')
fields['evt_precip'] = ('time_epoch',)
fields['evt_strike'] = ('time_epoch', 'distance', 'energy')
fields['obs_st'] = ('time_epoch', 'wind_lull', 'wind_avg', 'wind_gust', 'wind_direction', 'wind_sample_interval', 'station_pressure', 'air_temperature', 'relative_humidity', 'illuminance', 'uv', 'solar_radiation', 'rain_accumulated', 'precipitation_type', 'lightning_strike_avg_distance', 'lightning_strike_count', 'battery', 'report_interval')

def loader(config_dict, engine):
    return WeatherFlowUDPDriver(config_dict)

def mapToWeewxPacket(pkt, sensor_map, isRest, interval = 1):
    packet = dict()
    if 'time_epoch' in pkt:
        packet = {
            'dateTime': pkt['time_epoch'],
            'usUnits' : weewx.METRICWX
        }
    
    lightning_packet = None

    if isRest:
        packet.update({'interval':interval})

    # Correct distance value for lightning strikes when count was 0
    weatherflow_lightning_strike_count_key = None
    weatherflow_lightning_strike_avg_distance_key = None
    for weatherflow_key in pkt.keys():
        if weatherflow_key.find("lightning_strike_count") > -1:
            weatherflow_lightning_strike_count_key = weatherflow_key
        elif weatherflow_key.find("lightning_strike_avg_distance") > -1:
            weatherflow_lightning_strike_avg_distance_key = weatherflow_key
    
    if weatherflow_lightning_strike_count_key and weatherflow_lightning_strike_avg_distance_key:
        weight = pkt[weatherflow_lightning_strike_count_key]
        lightning_packet = dict()
        lightning_packet = {
            'dateTime': pkt['time_epoch'],
            'usUnits' : weewx.METRICWX,
            'weight' : weight
        }
        if pkt[weatherflow_lightning_strike_count_key] == 0:
            # If there was no strike the distance should be None and not 0 as used by weatherflow
            # Perhaps the weight of 0 for such events would be enough but a value of None makes things clearer
            pkt[weatherflow_lightning_strike_avg_distance_key] = None

    for pkt_weewx, pkt_label in sensor_map.items():
        for label in ensureList(pkt_label):
            if label.endswith('.rest') and isRest:
                label = label[:-5]
            elif label.endswith('.udp') and not isRest:
                label = label[:-4]
            if label.replace("-","_") in pkt:
                if lightning_packet and label.find("strike") > -1:
                    # This is a lightning strike event which has to be handled weighted when using an accumulator
                    # We only want to treat the lightning values weighted. Therefore we have to return a weighted lightning packet and
                    # an unweighted packet for non lightning values.
                    # TODO: This assertion was wrong due to a defect hardware: This only affects REST data, not UDP data, because weatherflow does not send cumulative strikes via UDP                        
                    lightning_packet[pkt_weewx] = pkt[label.replace("-","_")]
                else: 
                    packet[pkt_weewx] = pkt[label.replace("-","_")]
    
    return packet, lightning_packet    

def parseUDPPacket(pkt, calculator = None):
    packet = dict()
    if 'serial_number' in pkt:
        if 'type' in pkt:
            serial_number = pkt['serial_number'].replace("-","_")
            pkt_label = serial_number + "." + pkt['type']
            for key in pkt:
                packet[key + "." + pkt_label] = pkt[key]

            if pkt['type'] in ('obs_air', 'obs_sky', 'obs_st'):
                packet['time_epoch'] = pkt['obs'][0][0]
                for key, value in zip(fields[pkt['type']], pkt['obs'][0]):
                    packet[key + "." + pkt_label] = value
                    if key == "battery" and pkt['type'] == 'obs_st' and calculator:
                        calculator.addVoltage(value)
                        mode = calculator.getMode()
                        if mode != None:
                            packet["battery_mode." + pkt_label] = mode

            elif pkt['type'] == 'rapid_wind':
                packet['time_epoch'] = pkt['ob'][0]
                for key, value in zip(fields['rapid_wind'], pkt['ob']):
                    packet[key + "." + pkt_label] = value

            elif pkt['type'] in ('evt_strike', 'evt_precip'):
                packet['time_epoch'] = pkt['evt'][0]
                for key, value in zip(fields[pkt['type']], pkt['evt']):
                    packet[key + "." + pkt_label] = value

            elif pkt['type'] == 'device_status':
                packet['time_epoch'] = pkt['timestamp']

            elif pkt['type'] == 'hub_status':
                packet['time_epoch'] = pkt['timestamp']

            elif pkt['type'][0:2] == 'X_':
                packet['time_epoch'] = int(time.time())

            elif pkt['type'] not in ('light_debug') :
                logerr("Unknown packet type: '%s'" % pkt['type'])

        else:
            loginf('Corrupt UDP packet? %s' % pkt)
    else:
        loginf('Corrupt UDP packet? %s' % pkt)
    return packet

def getStationsUrl(token):
    return 'https://swd.weatherflow.com/swd/rest/stations?token={token}'.format(token = token)

def getObservationsUrl(start, end, token, device_id):
    return 'https://swd.weatherflow.com/swd/rest/observations/device/{device_id}?token={token}&time_start={start}&time_end={end}'.format(token = token, device_id = device_id, start = start, end = end)

def getStationDevices(token):
    if not token:
        return dict(), dict()
    response = requests.get(getStationsUrl(token))
    if (response.status_code != 200):
        raise DriverException("Could not fetch station information from WeatherFlow webservice: {}".format(response))
    stations = response.json()["stations"]
    device_id_dict = dict()
    device_dict = dict()
    for station in stations:
        for device in station["devices"]:
            if 'serial_number' in device:
                device_id_dict.update({device["device_id"]:device["serial_number"]})
                device_dict.update({device["serial_number"]:device["device_id"]})
    return device_id_dict, device_dict

def readDataFromWF(start, token, devices, device_dict, batch_size):
    isFinished = False
    while not isFinished: # end > calendar.timegm(datetime.utcnow().utctimetuple()):
        end = start + batch_size - 1
        lastTimestamp = None
        logdbg('Reading from {} to {}'.format(datetime.utcfromtimestamp(start), datetime.utcfromtimestamp(end)))
        results = list()
        timestamps = None
        for device in devices:
            logdbg('Reading for {} from {} to {}'.format(device, datetime.utcfromtimestamp(start), datetime.utcfromtimestamp(lastTimestamp or end)))
            response = requests.get(getObservationsUrl(start, lastTimestamp or end, token, device_dict[device]))
            if (response.status_code != 200):
                raise DriverException("Could not fetch records from WeatherFlow webservice: {}".format(response))
            jsonResponse = response.json()
            if lastTimestamp == None and jsonResponse['obs'] != None:
                lastTimestamp = sorted(jsonResponse['obs'], key = lambda i: i[0], reverse = True)[0][0]

            result = dict()
            result['device_id'] = jsonResponse['device_id']
            result['type'] = jsonResponse['type']
            observations = sorted((jsonResponse['obs'] or list()), key = lambda x : x[0])
            newTimestamps = [observation[0] for observation in observations]
            timestamps = timestamps or (timestamps or list()) + list(set(newTimestamps) - set(timestamps or list()))
            result['obs'] = dict(zip(newTimestamps, observations))

            results.append(result)
        combinedResult = dict()
        combinedResult['device_ids'] = [result['device_id'] for result in results]
        combinedResult['types'] = [result['type'] for result in results]
        combinedResult['obs'] = list()
        for timestamp in sorted(timestamps):
            observationsForTimestamp = list()
            for result in results:
                if 'obs' in result and timestamp in result['obs']:
                    observationsForTimestamp.append(result['obs'][timestamp])
                else:
                    observationsForTimestamp.append(None)
            combinedResult['obs'].append(observationsForTimestamp)

        yield combinedResult
        if end > calendar.timegm(datetime.utcnow().utctimetuple()):
            isFinished = True
        else:
            start = end if lastTimestamp == None else lastTimestamp + 1

def parseRestPacket(pkt, device_id_dict, calculator):
    label_list = list()
    pos = 0
    for device_id in pkt['device_ids']:        
        label_list.append(device_id_dict[device_id].replace("-","_") + "." + pkt['types'][pos])
        pos += 1
    fields_list = list()
    for type in pkt['types']:
        fields_list.append(fields[type])
    for observations in pkt['obs']:
        packet = dict()
        pos = 0
        for observation in observations:
            if observation == None:
                continue
            packet['time_epoch'] = observation[0]
            for key, value in zip(fields_list[pos], observation):
                packet[key + "." + label_list[pos]] = value
                if key == "battery" and label_list[pos].endswith(".obs_st"):
                    calculator.addVoltage(value)
                    mode = calculator.getMode()
                    if mode != None:
                        packet["battery_mode." + label_list[pos]] = mode
            pos += 1
        yield packet

def getDevices(devicesList, devices, token, printIt=False):
    if not token:
        return list()
    devicesList = ensureList(devicesList)
    result = list()
    for device in devicesList:
        if device != '':
            if device in devices:
                result.append(device.strip().upper())
            else:
                warning('Configured device {} is unknown. Skipped.'.format(device), printIt)
    if not result:
        raise DriverException("None of the configured devices ({}) were available for the given API-token. Aborting.".format(', '.join(devicesList)))
    return result

def isString(input):
    try:
        basestring
    except NameError:
        basestring = str
    return isinstance(input, basestring)

def ensureList(inputList):
    if isString(inputList):
        return [inputList]
    else:
        return inputList

def getSensorMap(devices, device_id_dict, printIt=False):
    fieldsDictionary = {
        'ST-':
            {
                'evt_strike.udp':
                {
                    # 'lightning_energy': 'energy',
                    # 'lightning_distance': 'distance',
                },
                'rapid_wind.udp':
                {
                    'windSpeed': 'wind_speed',
                    'windDir': 'wind_direction'
                },
                'obs_st.rest':
                {
                    # 'lightning_strike_count': 'lightning_strike_count',
                    # 'lightning_distance': 'lightning_strike_avg_distance',
                    'windSpeed': 'wind_avg',
                    'windDir': 'wind_direction',
                    'windGust': 'wind_gust',
                },
                'obs_st':
                {
                    'outTemp': 'air_temperature',
                    'outHumidity': 'relative_humidity',
                    'pressure': 'station_pressure',
                    'lightning_strike_count': 'lightning_strike_count',
                    'lightning_distance': 'lightning_strike_avg_distance',
                    'outTempBatteryStatus': 'battery',
                    'luminosity': 'illuminance',
                    'UV': 'uv',
                    'rain': 'rain_accumulated',
                    'radiation': 'solar_radiation',
                    'batteryStatus1': 'battery_mode'
                },
                'device_status':
                {
                    'signal1': 'rssi',
                    'signal2': 'hub_rssi'
                }
            },
        'AR-':
            {
                'obs_air':
                {
                    'outTemp': 'air_temperature',
                    'outHumidity': 'relative_humidity',
                    'pressure': 'station_pressure',
                    'lightning_strike_count': 'lightning_strike_count',
                    'lightning_distance': 'lightning_strike_avg_distance',
                    'outTempBatteryStatus': 'battery'
                }
            },
        'SK-':
            {
                'obs_sky':
                {
                    'windSpeed': 'wind_avg',
                    'windDir': 'wind_direction',
                    'windGust': 'wind_gust',
                    'luminosity': 'illuminance',
                    'UV': 'uv',
                    'rain': 'rain_accumulated',
                    'windBatteryStatus': 'battery',
                    'radiation': 'solar_radiation'
                }
            },
        'HB-':
            {
                'hub_status':
                {
                    'signal3': 'rssi'
                }
            }
    }
    configObj = ConfigObj()
    configObj['sensor_map'] = {}
    devices.reverse()
    for device in devices:
        if device not in device_id_dict.values():
            warning('Unknown device {}, skipping'.format(device), printIt)
            continue
        typeString = device[0:3]
        if typeString not in fieldsDictionary:
            warning('Unknown type for device {}' % device, printIt)
            continue
        errors = False
        for packageType in fieldsDictionary[typeString]:
            fields = fieldsDictionary[typeString][packageType]
            for field in fields:
                mapping = '{}.{}.{}'.format(fields[field], device, packageType)
                if field in configObj['sensor_map'].dict():
                    existingMapping = configObj['sensor_map'][field]
                    hasUdp = isString(existingMapping) and (packageType.endswith('.udp') or existingMapping.endswith('.udp'))
                    hasRest = isString(existingMapping) and (packageType.endswith('.rest') or existingMapping.endswith('rest'))
                    if hasUdp and hasRest:
                        mapping = [existingMapping, mapping]
                    else:
                        errors = True
                        warning('Cannot map field {} to {} as it is already set to \'{}\''.format(field, device, configObj['sensor_map'][field]), printIt)
                configObj['sensor_map'].update({field: mapping})
        if errors:
            warning('Mapping errors occurred. You should probably configure a manual sensor-map', printIt)
    return configObj['sensor_map']

def getHardwareName(devices):
    typeDict = { 
        'ST-':'Tempest',
        'AR-':'Air',
        'SK-':'Sky'
    }
    result = ''
    for device in devices:
        if device[:3] in typeDict:
            result = '%s/%s' % (result, typeDict[device[:3]]) if result != '' else typeDict[device[:3]]
    return '%s %s' % (HARDWARE_NAME, result)

def warning(warning, printIt):
    if printIt:
        print('Warning: {}'.format(warning))
    else:
        logwrn(warning)

class WeatherFlowUDPDriver(weewx.drivers.AbstractDevice):

    def __init__(self, all_dict):
        loginf('driver version is %s' % DRIVER_VERSION)
        stn_dict = all_dict[DRIVER_NAME]
        std_dict = all_dict['StdArchive']
        self._log_raw_packets = tobool(stn_dict.get('log_raw_packets', False))
        self._udp_address = stn_dict.get('udp_address', '<broadcast>')
        self._udp_port = int(stn_dict.get('udp_port', 50222))
        self._udp_timeout = int(stn_dict.get('udp_timeout', 90))
        self._share_socket = tobool(stn_dict.get('share_socket', False))
        self._sensor_map = stn_dict.get('sensor_map', None)
        self._token = stn_dict.get('token', '')
        self._batch_size = int(stn_dict.get('batch_size', 24 * 60 * 60))
        self._device_id_dict, self._device_dict = getStationDevices(self._token)
        self._devices = getDevices(stn_dict.get('devices', list(self._device_dict.keys())), self._device_dict.keys(), self._token)
        self._rest_enabled = tobool(stn_dict.get('rest_enabled', True))
        self._archive_interval = int(std_dict.get('archive_interval', 60))
        self._loopHiLo = tobool(std_dict.get('loop_hilo', True))
        self._archive_delay = int(std_dict.get('archive_delay', 15))
        if self._sensor_map == None:
            self._sensor_map = getSensorMap(self._devices, self._device_id_dict)
        self._calculator = BatteryModeCalculator()

        loginf('sensor map is %s' % self._sensor_map)
        loginf('*** Sensor names per packet type')

        for pkt_type in fields:
            loginf('packet %s: %s' % (pkt_type,fields[pkt_type]))

    def hardware_name(self):
        return getHardwareName(self._devices)

    def genLoopPackets(self):
        for udp_packet in self.gen_udp_packets():
            m2 = parseUDPPacket(udp_packet, self._calculator)
            # ignore packets immediately after the start of the hub when the hub
            # has not been initialized with a correct dateTime treating values below 1000
            # as obvious wrong values
            if 'time_epoch' in m2 and m2['time_epoch'] > 1000:
                m3_non_lightning, m3_lightning = mapToWeewxPacket(m2, self._sensor_map, False)
                m3_array = [m3_non_lightning, m3_lightning]
                for m3 in m3_array:
                    if len(m3) > 2:
                        logdbg('Import from UDP: %s' % datetime.utcfromtimestamp(m3['dateTime']))
                        yield m3
            else:
                if 'time_epoch' in m2:
                    logwrn("Ignoring packet with obviously uninitialized dateTime %s" % m2['time_epoch'])
                else:
                    logwrn("Ignoring packet without dateTime")

    def gen_udp_packets(self):
        """Yield raw UDP packets"""
        loginf('Listening for UDP broadcasts to IP address %s on port %s, with timeout %s and share_socket %s...'
               % (self._udp_address,self._udp_port,self._udp_timeout,self._share_socket))

        sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        try:
            if self._share_socket:
                sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.bind((self._udp_address,self._udp_port))
            sock.settimeout(self._udp_timeout)

            while True:
                try:
                    m0, host_info = sock.recvfrom(1024)
                except timeout:
                    logerr('Socket timeout waiting for incoming UDP packet!')
                else:
                    # Decode the JSON. Some base stations have emitted datagrams that are not pure UTF-8, so
                    # be prepared to catch the exception.
                    try:
                        m1 = json.loads(m0)
                    except UnicodeDecodeError:
                        loginf("Unable to decode packet %s" % m0)
                    else:
                        if self._log_raw_packets:
                            loginf('raw packet: %s' % m1)
                        yield m1
        finally:
            sock.close()

    def convertREST2weewx(self, packet):
        archivePeriod = None
        for observation in parseRestPacket(packet, self._device_id_dict, self._calculator):
            m3_non_lightning, m3_lightning = mapToWeewxPacket(observation, self._sensor_map, True, int((self._archive_interval + 59) / 60))
            m3_array = [m3_non_lightning, m3_lightning]
            for m3 in m3_array:
                if m3 and len(m3) > 3:
                    logdbg('Import from REST %s' % datetime.utcfromtimestamp(m3['dateTime']))
                    if self._archive_interval <= 60:
                        yield m3
                    else:
                        # Use an accumulator and treat REST API data like loop data
                        if not archivePeriod:
                            # init archivePeriod
                            archivePeriod = ArchivePeriod(weeutil.weeutil.startOfInterval(m3['dateTime'], self._archive_interval), self._archive_interval, self._archive_delay)
                        
                        if m3['dateTime'] >= archivePeriod._end_archive_delay_ts:
                            archivePeriod.startNextArchiveInterval(weeutil.weeutil.startOfInterval(m3['dateTime'], self._archive_interval))
                        
                        # Try adding the API packet to the existing accumulator. If the
                        # timestamp is outside the timespan of the accumulator, an exception
                        # will be thrown
                        try:
                            archivePeriod.addRecord(m3, add_hilo=self._loopHiLo)
                        except weewx.accum.OutOfSpan:
                            # Shuffle accumulators:
                            archivePeriod.startNextArchiveInterval()
                            # Try again:
                            archivePeriod.addRecord(m3, add_hilo=self._loopHiLo)  
            
                        archive_record = archivePeriod.getPreviousRecord()
                        if archive_record:
                            logdbg('Archiving accumulated data from REST %s' % archivePeriod._start_archive_period_ts)
                            yield archive_record
        if archivePeriod:
            archive_record = archivePeriod.getRecord()
            if archive_record:
                # return record from last processed accumulator 
                yield archive_record

    def genStartupRecords(self, since_ts):
        if since_ts == None:
            since_ts = int(time.time()) - 365 * 24 * 60 * 60

        if self._token != "" and self._rest_enabled:
            loginf('Reading from {}'.format(datetime.utcfromtimestamp(since_ts)))
            for packet in readDataFromWF(since_ts + 1, self._token, self._devices, self._device_dict, self._batch_size):
                for archive_record in self.convertREST2weewx(packet):
                    yield archive_record
        else:
            loginf('Skipped fetching from REST API')
            


class ArchivePeriod:
    def __init__(self, start_archive_period_ts, archive_interval, archive_delay):
        self._start_archive_period_ts = start_archive_period_ts
        self._archive_interval = archive_interval
        self._archive_delay = archive_delay
        self._end_archive_period_ts = self._start_archive_period_ts + self._archive_interval
        if (self._end_archive_period_ts > time.time()):
                self._end_archive_period_ts = int(time.time())
        self._end_archive_delay_ts = self._end_archive_period_ts + self._archive_delay
        self._accumulator = weewx.accum.Accum(weeutil.weeutil.TimeSpan(self._start_archive_period_ts, self._end_archive_period_ts))
        self._old_accumulator = None
        
    def startNextArchiveInterval(self, start_archive_period_ts):
        self._start_archive_period_ts = start_archive_period_ts
        self._end_archive_period_ts = self._start_archive_period_ts + self._archive_interval
        if (self._end_archive_period_ts > time.time()):
            self_end_archive_period_ts = int(time.time())
        self._end_archive_delay_ts = self._end_archive_period_ts + self._archive_delay
            
        (self._old_accumulator, self._accumulator) = \
        (self._accumulator, weewx.accum.Accum(weeutil.weeutil.TimeSpan(self._start_archive_period_ts, self._end_archive_period_ts)))
    
    def addRecord(self, record, add_hilo=True):
        weight = 1
        if "weight" in record:
            weight = record.pop("weight")
        self._accumulator.addRecord(record, add_hilo,weight)
    
    def getPreviousRecord(self):
        if (self._old_accumulator):
            record = self._old_accumulator.getRecord()
            self._old_accumulator = None
            return record
        
    def getRecord(self):
        return self._accumulator.getRecord()

class BatteryModeCalculator:
    def __init__(self):
        self._list = list()

    def addVoltage(self, value):
        self._list.append(value)
        if len(self._list) > 10:
            self._list.pop(0)

    def __isCharging(self):
        if len(self._list) == 10:
            firstValue = sum(self._list[0:5])
            secondValue = sum(self._list[5:10])
            return secondValue > firstValue
        else:
            return False

    def getMode(self):
        if len(self._list) == 0:
            return None
        currentValue = sum(self._list[-5:]) / len(self._list[-5:])
        if self.__isCharging():
            if currentValue >= 2.455:
                return 0
            elif currentValue >= 2.41:
                return 1
            elif currentValue >= 2.375:
                return 2
            else:
                return 3
        else:
            if currentValue <= 2.355:
                return 3
            elif currentValue <= 2.39:
                return 2
            elif currentValue <= 2.415:
                return 1
            else:
                return 0        

if __name__ == '__main__':
    import optparse
    import weeutil.logger
    from weeutil.weeutil import to_sorted_string

    weewx.debug = 2

    weeutil.logger.setup('weatherflow', {})

    usage = """Usage: python -m weatherflow --help
       python -m weatherflow --version
       python -m weatherflow --create-sensor-map --token=TOKEN [--devices=DEVICES]
       python -m weatherflow [--host=HOST] [--port=PORT] [--timeout=TIMEOUT] [--share-socket]
                             [--hide-raw] [--hide-parsed]"""

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', action='store_true',
                      help='Display driver version')
    parser.add_option('--address', default='255.255.255.255',
                      help='UDP address to use. Default is "255.255.255.255".',
                      metavar="ADDR")
    parser.add_option('--port', type="int", default=50222,
                      help='Socket port to use. Default is "50222"',
                      metavar="PORT")
    parser.add_option('--timeout', type="int", default=20,
                      help="How long to wait for a packet.")
    parser.add_option('--share-socket', default=False, action="store_true",
                      help="Allow another process to access the port.")
    parser.add_option('--hide-raw', default=False, action='store_true',
                      help="Do not show raw UDP packets.")
    parser.add_option('--hide-parsed', default=False, action='store_true',
                      help="Do not show parsed UDP packets.")
    parser.add_option('--create-sensor-map', action='store_true',
                      help="Generate a sensor-map.")
    parser.add_option('--token',
                      help="Provide API token for WeatherFlow API.",
                      metavar="TOKEN")
    parser.add_option('--devices',
                      help='Provide devices (comma-separated) to use for the sensor-map.',
                      metavar='DEVICES', default='')
    (options, args) = parser.parse_args()

    if options.version:
        print("Weatherflow driver version %s" % DRIVER_VERSION)
        exit(0)

    if options.create_sensor_map:
        if not options.token:
            print('Please provide an API token with the --token=TOKEN option')
            exit(1)
        try:
            device_id_dict, device_dict = getStationDevices(options.token)
            devicesList = [s.strip() for s in options.devices.split(',')] if ',' in options.devices else options.devices if len(options.devices) > 0 else list(device_dict.keys())
            devices = getDevices(devicesList, device_dict.keys(), options.token, True)
            sensor_map = getSensorMap(devices, device_id_dict, True)
            print('Sensor map:')
            print('')
            print('    [[sensor_map]]')
            for key in sensor_map.keys():
                if isinstance(sensor_map[key], list):
                    print('        {} = {}'.format(key, ', '.join(sensor_map[key])))
                else:
                    print('        {} = {}'.format(key, sensor_map[key]))
            print('')
            print('You can copy the above into your weewx.conf file directly after your [WeatherFlowUDP] section')
            exit(0)
        except DriverException as ex:
            print('Error: {}'.format(ex))
            exit(1)

    print("Using address '%s' on port %d" % (options.address, options.port))

    config_dict = {
        'WeatherFlowUDP': {
            'address': options.address,
            'port': options.port,
            'timeout': options.timeout,
            'share_socket': options.share_socket,
        },
        'StdArchive' : { }
    }

    device = loader(config_dict, None)

    for pkt in device.gen_udp_packets():
        if not options.hide_raw:
            print('raw:', pkt)
        parsed = parseUDPPacket(pkt)
        if not options.hide_parsed:
            print('parsed:', to_sorted_string(parsed))
