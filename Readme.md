# weatherflow-udp
Copyright 2017-2020 Arthur Emerson, <vreihen@yahoo.com><br>
Copyright 2021 Jan-Jaap van der Geer, <jjvdgeer@yahoo.com><br>
Copyright 2022 edi-x
Distributed under terms of the GPLv3

This is a driver for weewx, that captures data from the WeatherFlow bridge via the bridge's UDP broadcasts on the local subnet. In addition, it can fetch data from the WeatherFlow REST API when first starting, so that missing data since the previous run of weewx will be fetched as well.

# Installation

Installation should be as simple as grabbing a .ZIP download of this entire project from the GitHub web interface, and then running this command:

```
wee_extension --install weatherflow-udp-master.zip
```

Worst case, a manual install is simple enough.  At least on my Raspberry Pi, copy weatherflowudp.py from bin/user to /usr/share/weewx/user/weatherflowudp.py, and then edit /etc/weewx/weewx.conf and add the new station driver settings per the info below.

(If you are starting with a fresh weewx installation, choose the "Simulator" station driver during the package install process.  The wee_extension command above will replace the simulator station driver with this one.)

# Configuration

The driver needs some configuration. The best way to get started is to add the following section to the weewx.conf file, for example just **before** the section that starts with the line:

```
[Simulator]
```

Add the following text before the above line in the weewx.conf:

```
[WeatherFlowUDP]
    driver = user.weatherflowudp
    token = <your token>
```

However, you need to change the last line and update it with a token from your own weather station. To obtain a token go to <https://tempestwx.com/>, log in and navigate to Settings, More, Data Authorizations. Or go directly to <https://tempestwx.com/settings/tokens> while logged in. From there, press Create Token. Give it a name and press 'Create Token'. Copy the aquired token and add it into the section above, so that it reads something like this:

```
    token = 79ebd9e8-4242-4a58-bd76-40fa50d894ce
```

When this is done you need to tell weewx to use the WeatherFlow driver. This is done by setting the station_type variable in the [Station] section near the top to 'WeatherFlowUDP', like this:

```
    station_type = WeatherFlowUDP
```

For most setups this is all you have to do. However if you have more than a single Tempest or a set with Air & Sky or you just want to do more advanced things you might want to look through the rest of this section.

## Options

```
    token = 79ebd9e8-4242-4a58-bd76-40fa50d894ce
```

As mentioned above, this configuration is needed if you want the driver to fetch information from the REST interface. This has two purposes. First, it is needed to fetch sensor data from the REST API. Second, it enables you to fetch information about your weather station so that it can automatically configure your sensor map (see below).

You can leave this option out if you do not want to use the REST API to fetch sensor data and you provide your own sensor map.

```
    rest_enabled = False
```

If you do not want to fetch data from the REST API interface but you still want the sensor map to be configured automatically, then you can set this option to False. If you leave it out or set it to True, it will use the REST API (provided you have provided the token).

```
    devices = SK-12345678,AR-12345678
```

If you have multiple weather stations/sensor units you might want to provide this configuration option. It is a comma separated list of the serial numbers of your sensor units. The effect of this configuration is that the generated sensor map is restricted to the usage of the sensor units mentioned here.

Should you have sensor units with overlapping sensors the sensor unit mentioned first will be preferred in the generated sensor map.

```
[WeatherflowCloudDataService]
    devices = ST-12345678
    enhanced_readings = lightning_strike_count, lightning_distance, rain, rainRate
    request_timeout = 10

[Engine]
    [[Services]]
        data_services = user.weatherflowudp.WeatherflowCloudDataService
        process_services = user.weatherflowudp.WeatherflowConvert, user.weatherflowudp.WeatherflowCalibrate, user.weatherflowudp.WeatherflowQC, weewx.wxservices.StdWXCalculate
        archive_services = user.weatherflowudp.WeatherFlowUDPArchive
```

If you have enabled the REST API like described above, the driver will collect historical data from weatherflow if the station was offline for a while. If you want to enrich your loop data with the enhanced values from weatherflow, you will need this additional service configuration.

Here is a short explanation for the configured services:

user.weatherflowudp.WeatherflowCloudDataService: To use the values from the weatherflow API instead of the aggregated values from the loop. This can increase the data quality especially for lightning an rain values. Only the readings listed in "enhanced_readings" will be substituted by the REST data. The device parameter is optional and can be used to collect readings for a subset of the devices defined in the driver.

user.weatherflowudp.WeatherflowConvert/WeatherflowCalibrate/WeatherflowQC: Are required to perform conversions, calibrations and QC on values collected from the weatherflow API

user.weatherflowudp.WeatherFlowUDPArchive: Initializes the archive process after the required data is available at weatherflows API. Usually this takes less than a minute but sometimes even longer.

```
    log_raw_packets = False
```

Enable writing all raw UDP packets received to syslog, (or wherever weewx is configured to send log info).  Will fill up your logs pretty quickly, so only use it as a debugging tool or to identify sensors.

```
    udp_address = <broadcast>
    # udp_address = 0.0.0.0
    # udp_address = 255.255.255.255
```

This is the broadcast address that we should be listening on for packets. If the driver throws an error on start, try one of the other commented-out options (in order). This seems to be platform-specific. All three work on Debian Linux and my Raspberry Pi, but only 0.0.0.0 works on my Macbook running OS-X or MacOS. Don't ask about Windows, since I don't have a test platform to see if it will even work.

```
    udp_port = 50222
```

The IP port that we should be listening for UDP packets from. WeatherFlow's default is 50222.

```
    udp_timeout = 90
```

The number of seconds that we should wait for an incoming packet on the UDP socket before we give up and log an error into syslog. I cannot determine whether or not weewx cares whether a station driver is non-blocking or blocking, but encountered a situation in testing where the WeatherFlow Hub rebooted for a firmware update and it caused the driver to throw a timeout error and exit. I have no idea what the default timeout value even is, but decided to make it configurable in case it is important to someone else.  My default of 90 seconds seems reasonable, with the Air sending observations every 60 seconds. If you are an old-school programmer like me who thinks that computers should wait forever until they receive data, the Python value "None" should disable the timeout. In any case, the driver will just log an error into syslog and keep on processing. It isn't like it is the end of the world if you pick a wrong value, but you may have a better chance of missing packets during the brief error trapping time with a really short duration.

```
    share_socket = False
```

Whether or not the UDP socket should be shared with other local programs also listening for WeatherFlow packets. Default is False because I suspect that some obscure Python implementation will have problems sharing the socket. Feel free to set it to True if you have other apps running on your weewx host listening for WF UDP packets.

## Sensor Map

This driver detects different sensors packets broadcast using the WeatherFlow UDP JSON protocol, and it includes a mechanism to filter the incoming data and map the filtered data onto the weewx database schema and identify the type of data from each sensor.

Sensors are filtered based on a tuple that identifies uniquely each sensor. A tuple consists of the observation name, a unique identifier for the hardware, and the packet type, separated by periods, which is mapped to a particular weewx field:

```
<weewx_field> = <observation_name>.<hardware_id>.<packet_type>
```

The filter and data types are specified in a sensor_map stanza in the driver stanza in your weewx.conf file.  For example, on an Air/Sky setup:

```
[WeatherFlowUDP]
    driver = user.weatherflowudp
    log_raw_packets = False
    udp_address = <broadcast>
    # udp_address = 0.0.0.0
    # udp_address = 255.255.255.255
    udp_port = 50222
    udp_timeout = 90
    share_socket = False

    [[sensor_map]]
        outTemp = air_temperature.AR-00004444.obs_air
        outHumidity = relative_humidity.AR-00004444.obs_air
        pressure = station_pressure.AR-00004444.obs_air
        lightning_strike_count = lightning_strike_count.AR-00004444.obs_air
        lightning_distance = lightning_strike_avg_distance.AR-00004444.obs_air
        # lightning_strike_count = lightning_strike_count.AR-00004444.evt_strike
        # lightning_distance = lightning_strike_avg_distance.AR-00004444.evt_strike
        outTempBatteryStatus = battery.AR-00004444.obs_air
        windSpeed = wind_avg.SK-00001234.obs_sky
        windDir = wind_direction.SK-00001234.obs_sky
        # windSpeed = wind_avg.SK-00001234.rapid_wind
        # windDir = wind_direction.SK-00001234.rapid_wind
        windGust = wind_gust.SK-00001234.obs_sky
        luminosity = illuminance.SK-00001234.obs_sky
        UV = uv.SK-00001234.obs_sky
        rain = rain_accumulated.SK-00001234.obs_sky
        windBatteryStatus = battery.SK-00001234.obs_sky
        radiation = solar_radiation.SK-00001234.obs_sky
```

This sensor map has several mappings commented out. These are alternative mappings that give the same information through other types of packages. All sensors are reported every minute, but for some sensors, like the wind sensor, there is also a specialised package that is emitted much more frequently. The package with all the sensors contains the accumulated data, but you might want to fetch the data from the specialised packages and let weewx do the accumulation.

However, since these specialised packages are not available through the REST API, mapping these will cause problems when fetching through the REST API and the fields would not get filled. Therefore it is not recommended to do this unless you are only fetching from the UDP packages.

The sensor map can be generated by running the driver directly. For more information see below.

If you want to collect lightning data, please add the following accumulator configuration:

```
[Accumulator]
    [[lightning_strike_count]]
        extractor = sum
    [[lightning_distance]]
        adder=add_lightning

    #Optional fields:

    #If you add this field to your database as TEXT field, the driver will add the lightning events in a json structure
    [[lightningPerTimestamp]]
        accumulator=json
        adder=add_json
        extractor=json_array
```

## Running the driver directly

It is possible to run the driver directly. There are several purposes why you would want to do this:
* Finding out if the driver can receive the UDP packages
* Finding out what sensors/units are available by looking at the UDP packages
* Generating a sensor map
* Finding out what version the driver has

### How to run the driver directly

To run the driver directly you need to provide the PYTHON path to tell python where weewx is located. See the following example which opens a help page showing the options provided by the driver when it is run directly. In the examples we assume that weewx is located in /home/weewx. If your installation is located elsewhere, you'll need to change this when running the commands.

```
cd /home/weewx
PYTHONPATH=./bin python ./bin/user/weatherflowudp.py --help
```

### Finding out if the driver can receive the UDP packages

Run the following command:
```
cd /home/weewx
PYTHONPATH=./bin python ./bin/user/weatherflowudp.py
```

For every package received, you will see the raw JSON package and the parsed package (which uses the sensor map format). See this example from a Tempest weather station:

```
Using address '255.255.255.255' on port 50222
raw: {'serial_number': 'ST-12345678', 'type': 'obs_st', 'hub_sn': 'HB-12121212', 'obs': [[1611872941, 0.22, 1.01, 2.01, 40, 3, 1008.32, -10.21, 87.92, 5, 0.0, 0, 0.0, 0, 0, 0, 2.675, 1]], 'firmware_revision': 134}
parsed: air_temperature.ST_12345678.obs_st: -10.21, battery.ST-12345678.obs_st: 2.675, firmware_revision.ST-12345678.obs_st: 134, hub_sn.ST-12345678.obs_st: HB-12121212, illuminance.ST-12345678.obs_st: 5, lightning_strike_avg_distance.ST-12345678.obs_st: 0, lightning_strike_count.ST-12345678.obs_st: 0, obs.ST-12345678.obs_st: [[1611872941, 0.22, 1.01, 2.01, 40, 3, 1008.32, -10.21, 87.92, 5, 0.0, 0, 0.0, 0, 0, 0, 2.675, 1]], precipitation_type.ST-12345678.obs_st: 0, rain_accumulated.ST-12345678.obs_st: 0.0, relative_humidity.ST-12345678.obs_st: 87.92, report_interval.ST-12345678.obs_st: 1, serial_number.ST-12345678.obs_st: ST-12345678, solar_radiation.ST-12345678.obs_st: 0, station_pressure.ST-12345678.obs_st: 1008.32, time_epoch: 1611872941, time_epoch.ST-12345678.obs_st: 1611872941, type.ST-12345678.obs_st: obs_st, uv.ST-12345678.obs_st: 0.0, wind_avg.ST-12345678.obs_st: 1.01, wind_direction.ST-12345678.obs_st: 40, wind_gust.ST-12345678.obs_st: 2.01, wind_lull.ST-12345678.obs_st: 0.22, wind_sample_interval.ST-12345678.obs_st: 3
```

If you do not want to see the raw messages you can provide --hide-raw and if you do not want to see the parsed messages you can provide --hide-parsed.

### Finding out what sensors/units are available by looking at the UDP packages

See the above section. By looking at the results you can see what readings are actually showing up and what is available.

### Generating a sensor map

If you want to have a starting point for creating your own sensor map you can let the driver generate one for you which you then can copy into the weewx.conf file. To generate the sensor map, use the following command:

```
cd /home/weewx
PYTHONPATH=./bin python ./bin/user/weatherflowudp.py \
  --create-sensor-map --token=79ebd9e8-4242-4a58-bd76-40fa50d894ce
```

The token in the example (79ebd9e8-4242-4a58-bd76-40fa50d894ce) needs to be replaced with your actual token.

Usually this will work, or if it does not it will report the problems it finds. If you have multiple devices you may need to list the ones you want to use to create your map by adding ```--devices=<comma separated list of devices' serial numbers>``` to the command line. For example:

```
cd /home/weewx
PYTHONPATH=./bin python ./bin/user/weatherflowudp.py \
  --create-sensor-map --token=79ebd9e8-4242-4a58-bd76-40fa50d894ce \
  --devices=SK-12345678,AR-12345678
```

### Finding out what version the driver has

To find out what version the driver has, do the following:

```
cd /home/weewx
PYTHONPATH=./bin python ./bin/user/weatherflowudp.py --version
```

## Various

To identify the various observation_name options, start weewx with this station driver installed and it will write the entire matrix of available observation_names and sensor_types to syslog (or wherever weewx is configured to send log info).

Apologies for the long observation_names, but I figured that it would be best if I used the documented field names from WeatherFlow's UDP packet specs (v37 at the time of writing) with underscores between words so that the names were consistent with their protocol documentation. See https://weatherflow.github.io/Tempest/api/udp.html

## Thanks

Finally, let me add a thank you to Matthew Wall for the sensor map naming logic that I borrowed from his weewx-SDR station driver code: 

https://github.com/matthewwall/weewx-sdr

I guess that I should also thank David St. John and the "dream team" at WeatherFlow for all of the hard work and forethought that they put into making this weather station a reality.  I can't sing enough praises for whoever came up with the idea to send observation packets out live via UDP broadcasts, and think that they should be nominated for a Nobel Prize or something.

This is the part where I am supposed to put in a PayPal link and ask for donations if you find this code useful.  Since I am financially solvent (and would starve to death if I had to make a living as a programmer), :-)  I would like to encourage anyone reading this to make a small donation to a local not-for-profit school, hospital, animal shelter, or other charity of your choice who appreciates philanthropic support.
