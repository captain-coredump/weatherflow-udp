# installer for the weatherflow-udp driver
# Copyright 2017-2020 Arthur Emerson, vreihen@yahoo.com
# Distributed under the terms of the GNU Public License (GPLv3)

# modified installer derived from the weewx Belchertown skin installer
# https://raw.githubusercontent.com/poblabs/weewx-belchertown/master/install.py
# Copyright Pat O'Brien

import configobj
from setup import ExtensionInstaller

try:
    # Python 2
    from StringIO import StringIO
except ImportError:
    # Python 3
    from io import StringIO

#-------- extension info -----------

VERSION      = "1.10.2"
NAME         = 'weatherflowudp'
DESCRIPTION  = 'Capture data from WeatherFlow Bridge via UDP broadcast packets'
AUTHOR       = "Arthur Emerson"
AUTHOR_EMAIL = "vreihen@yahoo.com"

#-------- main loader -----------

def loader():
    return WeatherFlowUDPInstaller()

class WeatherFlowUDPInstaller(ExtensionInstaller):
    def __init__(self):
        super(WeatherFlowUDPInstaller, self).__init__(
            version=VERSION,
            name=NAME,
            description=DESCRIPTION,
            author=AUTHOR,
            author_email=AUTHOR_EMAIL,
            config=config_dict,
            files=files_dict
        )

#----------------------------------
#         config stanza
#----------------------------------

extension_config = """

[WeatherFlowUDP]

    driver = user.weatherflowudp
    log_raw_packets = False
    udp_address = <broadcast>
    # udp_address = 0.0.0.0
    # udp_address = 255.255.255.255
    udp_port = 50222
    udp_timeout = 90
    share_socket = False

    #
    # IMPORTANT - please edit in 'your' sensor ID below
    #             (the value 'ST-00000025' here is an example only)
    #

    [[sensor_map]]
        outTemp = air_temperature.ST-00000025.obs_st
        outHumidity = relative_humidity.ST-00000025.obs_st
        pressure = station_pressure.ST-00000025.obs_st
        # lightning_strikes =  lightning_strike_count.ST-00000025.obs_st
        # avg_distance =  lightning_strike_avg_distance.ST-00000025.obs_st
        outTempBatteryStatus = battery.ST-00000025.obs_st
        windSpeed = wind_speed.ST-00000025.rapid_wind
        windDir = wind_direction.ST-00000025.rapid_wind
        # luxXXX = illuminance.ST-00000025.obs_st
        UV = uv.ST-00000025.obs_st
        rain = rain_accumulated.ST-00000025.obs_st
        windBatteryStatus = battery.ST-00000025.obs_st
        radiation = solar_radiation.ST-00000025.obs_st
        # lightningXXX = distance.ST-00000025.evt_strike
        # lightningYYY = energy.ST-00000025.evt_strike

"""
config_dict = configobj.ConfigObj(StringIO(extension_config))

#----------------------------------
#        files stanza
#----------------------------------
files=[('bin/user', ['bin/user/weatherflowudp.py'])]
files_dict = files

#---------------------------------
#          done
#---------------------------------
