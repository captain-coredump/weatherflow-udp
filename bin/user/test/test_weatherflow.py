'''
Created on 06.04.2021

@author: edi-x
'''
import unittest
import os.path
import configobj
import sys
import time
import weewx
from user import weatherflowudp
from weewx import engine
from weewx.engine import StdArchive
from user.weatherflowudp import getStationDevices
#import user.weatherflowudp.WeatherFlowUDPDriver


# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "test.conf")

class Test(unittest.TestCase):


    def setUp(self):
        global config_path

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
            stn_dict = self.config_dict['WeatherFlowUDP']
            self.request_timeout = float(stn_dict.get('request_timeout', 30))
            self.token = stn_dict.get('token', '')
            self.device_id_dict, self.device_dict = weatherflowudp.getStationDevices(self.token, self.request_timeout)
            self.devices = weatherflowudp.getDevices(stn_dict.get('devices', list(self.device_dict.keys())), self.device_dict.keys(), self.token)
        
        except IOError:
            print("Unable to open configuration file %s" % config_path, file=sys.stderr)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            print("Error while parsing configuration file %s" % config_path, file=sys.stderr)
            raise

        self.driver = weatherflowudp.WeatherFlowUDPDriver(self.config_dict)
        # get first ST device_id
        for k in self.driver._device_id_dict.keys():
            if self.driver._device_id_dict[k].startswith("ST"):
                self.device_id = k
                self.device_name = self.driver._device_id_dict[k]
                break
            
        self.obs1 = [[1617299160, 0, 0, 0, 0, 3, 964, 18.8, 45, 26, 0, 0, 0, 0, 21, 2, 2.73, 1, 0, None, None, 0]]
        self.obs2 = [[1617299220, 0, 0, 0, 0, 3, 964, 18.7, 45, 19, 0, 0, 0, 0, 38, 1, 2.73, 1, 0, None, None, 0]]
        self.obs3 = [[1617299280, 0, 0.2, 1.03, 114, 3, 964, 18.7, 45, 14, 0, 0, 0, 0, 20, 2, 2.73, 1, 0, None, None, 0]]
        self.obs4 = [[1617299340, 0, 0.09, 0.8, 138, 3, 964.1, 18.6, 45, 11, 0, 0, 0, 0, 38, 1, 2.73, 1, 0, None, None, 0]]
        self.obs5 = [[1617299400, 0, 0.02, 0.31, 222, 3, 964.1, 18.6, 45, 8, 0, 0, 0, 0, 24, 1, 2.73, 1, 0, None, None, 0]]

        self.obs6 = [[1617299460, 0, 0, 0, 0, 3, 964.1, 18.6, 45, 6, 0, 0, 0, 0, 0, 0, 2.73, 1, 0, None, None, 0]]
        self.obs7 = [[1617299520, 0, 0.11, 0.85, 98, 3, 964.1, 18.6, 46, 4, 0, 0, 0, 0, 0, 0, 2.73, 1, 0, None, None, 0]]
        self.obs8 = [[1617299580, 0, 0.31, 1.03, 92, 3, 964.2, 18.5, 46, 5, 0, 0, 0, 0, 38, 1, 2.73, 1, 0, None, None, 0]]
        self.obs9 = [[1617299640, 0, 0.1, 0.8, 98, 3, 964.2, 18.5, 48, 4, 0, 0, 0, 0, 22, 1, 2.73, 1, 0, None, None, 0]]
        self.obs10 = [[1617299700, 0, 0.18, 0.8, 109, 3, 964.2, 18.5, 48, 4, 0, 0, 0, 0, 33, 1, 2.73, 1, 0, None, None, 0]]
        self.obs11 = [[1617299760, 0, 0.18, 0.8, 109, 3, 964.2, 18.5, 48, 4, 0, 0, 0, 0, 0, 0, 2.73, 1, 0, None, None, 0]]
  
        self.strike1 = [1617299140, 24, 123]
        self.strike2 = [1617299149, 18, 123]
        self.strike3 = [1617299186, 38, 123]
        self.strike4 = [1617299239, 25, 123]
        self.strike5 = [1617299245, 15, 123]
        self.strike6 = [1617299315, 38, 123]
        self.strike7 = [1617299368, 24, 123]
        self.rapid_wind1 = [1617299170, 2.5, 180]

    def tearDown(self):
        pass

    def checkResult(self, archive_record):
        
            if (archive_record["dateTime"] == 1617299400):
                assert round(archive_record["interval"],0) == 5
                assert round(archive_record["outTemp"],2) == 18.68
                assert round(archive_record["outHumidity"],1) == 45.0 
                assert round(archive_record["pressure"],2) == 964.04
                assert round(archive_record["windSpeed"],3) == 0.062
                assert round(archive_record["windDir"],2) == 125.39
                assert round(archive_record["windLull"],2) == 0.00
                assert round(archive_record["luminosity"],2) == 15.6
                assert round(archive_record["rain"],2) == 0.00
                assert round(archive_record["radiation"],2) == 0.00
                assert round(archive_record["UV"],2) == 0.00
                assert round(archive_record["lightning_strike_count"],2) == 7.00
#                assert round(archive_record["lightning_distance"],1) == 26.0
                assert round(archive_record["supplyVoltage"],2) == 2.73
            elif (archive_record["dateTime"] == 1617299700):
                assert round(archive_record["interval"],0) == 5
                assert round(archive_record["outTemp"],2) == 18.54
                assert round(archive_record["outHumidity"],1) == 46.6 
                assert round(archive_record["pressure"],2) == 964.16
                assert round(archive_record["windSpeed"],3) == 0.140
                assert round(archive_record["windDir"],2) == 98.16
                assert round(archive_record["windLull"],2) == 0.00
                assert round(archive_record["luminosity"],2) == 4.60
                assert round(archive_record["rain"],2) == 0.00
                assert round(archive_record["radiation"],2) == 0.00
                assert round(archive_record["UV"],2) == 0.00
                assert round(archive_record["lightning_strike_count"],2) == 3.00
#                assert round(archive_record["lightning_distance"],2) == 31.00
                assert round(archive_record["supplyVoltage"],2) == 2.73
            else:
                # invalid timestamp
                assert False

    # rename to testRESTConnection if you want to test a real REST connection
    def ztestRESTConnection(self):
        driver = weatherflowudp.WeatherFlowUDPDriver(self.config_dict)
        for archive_record in driver.genStartupRecords(int(time.time()-330)):
            print(archive_record)

        pass      
        
    def ztestSimulatedRESTData(self):
        
        result = dict()
        result['device_ids'] = [self.device_id]
        result['types'] = ['obs_st']
        result['obs'] = (self.obs1, self.obs2, self.obs3, self.obs4, self.obs5, self.obs6,
                          self.obs7, self.obs8, self.obs9, self.obs10)
        for archive_record in self.driver.convertREST2weewx(result):
            self.checkResult(archive_record)

    def testLoopPacket(self):
        
        test_engine = engine.StdEngine(self.config_dict)
        test_engine.console = TestConsole(self)
        try:
            test_engine.run()
        except EndLoop:
            pass
        
    def testRESTData(self):
        for packet in weatherflowudp.readDataFromWF(1650805200, 1650805800, self.token, self.devices, self.device_dict, (24 * 60 * 60), 20, 1, 0):
            for archive_record in self.driver.convertREST2weewx(packet):
                    print(packet)
            
class TestArchive(StdArchive):
    """Service that archives LOOP and archive data in the SQL databases."""
    
    def __init__(self, engine, config_dict):
        super(TestArchive, self).__init__(engine, config_dict)
    
    def _catchup(self, generator):
        pass
        
    def new_archive_record(self, event):
        """Called when a new archive record has arrived.
        Put it in the archive database."""
        self.engine.console.checkResult(event.record)
        #if (event.record["dateTime"] == 1617299400):
         #   assert round(event.record["lightning_event_count"],0) == 7

    def _software_catchup(self):
        # Extract a record out of the old accumulator. 
        record = self.old_accumulator.getRecord()
        # Add the archive interval
        record['interval'] = self.archive_interval / 60
        # Send out an event with the new record:
        self.engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD,
                                              record=record,
                                              origin='software'))

class TestConsole(object):
    """A dummy console, used to offer an archive_interval."""
    
    def __init__(self, test_instance):
        try:
            self.archive_interval = int(test_instance.config_dict['StdArchive']['archive_interval'])
            self._request_timeout = 30
            self._token = test_instance.config_dict['WeatherFlowUDP']['token']
            self._device_id_dict, self._device_dict = getStationDevices(self._token, self._request_timeout)
        except KeyError:
            self.archive_interval = 300
        self.test_instance = test_instance    
        
    def genStartupRecords(self, since_ts):
        pass
    
    def getTime(self):
        return 1617299101   
    
    def checkResult(self,archive_record):
        self.test_instance.checkResult(archive_record)
    
    def genLoopPackets(self):
        m1_list = ({'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike1, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike2, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs1, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike3, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'rapid_wind', 'hub_sn': 'HB-12345678', 'ob': self.test_instance.rapid_wind1, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs2, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike4, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike5, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs3, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike6, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs4, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'evt_strike', 'hub_sn': 'HB-12345678', 'evt': self.test_instance.strike7, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs5, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs6, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs7, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs8, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs9, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs10, 'firmware_revision': 134},
                   {'serial_number': self.test_instance.device_name, 'type': 'obs_st', 'hub_sn': 'HB-12345678', 'obs': self.test_instance.obs11, 'firmware_revision': 134},
                )
        for m1 in m1_list:
            m2 = weatherflowudp.parseUDPPacket(m1, self.test_instance.driver._calculator)
            m3 = weatherflowudp.mapToWeewxPacket(m2, self.test_instance.driver._sensor_map, False, 1, True)
            if (m3 and len(m3) > 2):
                yield m3
        
        raise EndLoop

    def closePort(self):
        pass

class EndLoop(Exception):
    """Exception to quit the test loop"""
    
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()