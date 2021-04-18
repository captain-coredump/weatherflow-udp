'''
Created on 06.04.2021

@author: edi-x
'''
import unittest
import os.path
import configobj
import sys
import time
import user.weatherflowudp
#import user.weatherflowudp.WeatherFlowUDPDriver


# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "test.conf")

class Test(unittest.TestCase):


    def setUp(self):
        global config_path

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
        except IOError:
            print("Unable to open configuration file %s" % config_path, file=sys.stderr)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            print("Error while parsing configuration file %s" % config_path, file=sys.stderr)
            raise


    def tearDown(self):
        pass


    def testUDP(self):
        driver = user.weatherflowudp.WeatherFlowUDPDriver(self.config_dict)
        for archive_record in driver.genStartupRecords(int(time.time()-330)):
            print(archive_record)
        
        
    def testUDPCalculations(self):
        driver = user.weatherflowudp.WeatherFlowUDPDriver(self.config_dict)
        
        obs1 = [[1617299160, 0, 0, 0, 0, 3, 964, 18.8, 45, 26, 0, 0, 0, 0, 21, 2, 2.73, 1, 0, None, None, 0]]
        obs2 = [[1617299220, 0, 0, 0, 0, 3, 964, 18.7, 45, 19, 0, 0, 0, 0, 38, 1, 2.73, 1, 0, None, None, 0]]
        obs3 = [[1617299280, 0, 0.2, 1.03, 114, 3, 964, 18.7, 45, 14, 0, 0, 0, 0, 20, 2, 2.73, 1, 0, None, None, 0]]
        obs4 = [[1617299340, 0, 0.09, 0.8, 138, 3, 964.1, 18.6, 45, 11, 0, 0, 0, 0, 38, 1, 2.73, 1, 0, None, None, 0]]
        obs5 = [[1617299400, 0, 0.02, 0.31, 222, 3, 964.1, 18.6, 45, 8, 0, 0, 0, 0, 24, 1, 2.73, 1, 0, None, None, 0]]
        
        obs6 = [[1617299460, 0, 0, 0, 0, 3, 964.1, 18.6, 45, 6, 0, 0, 0, 0, 0, 0, 2.73, 1, 0, None, None, 0]]
        obs7 = [[1617299520, 0, 0.11, 0.85, 98, 3, 964.1, 18.6, 46, 4, 0, 0, 0, 0, 0, 0, 2.73, 1, 0, None, None, 0]]
        obs8 = [[1617299580, 0, 0.31, 1.03, 92, 3, 964.2, 18.5, 46, 5, 0, 0, 0, 0, 38, 1, 2.73, 1, 0, None, None, 0]]
        obs9 = [[1617299640, 0, 0.1, 0.8, 98, 3, 964.2, 18.5, 48, 4, 0, 0, 0, 0, 22, 1, 2.73, 1, 0, None, None, 0]]
        obs10 = [[1617299700, 0, 0.18, 0.8, 109, 3, 964.2, 18.5, 48, 4, 0, 0, 0, 0, 33, 1, 2.73, 1, 0, None, None, 0]]

        # get device_id - assumes that only one device is configured in test.conf!
        for k in driver._device_id_dict.keys():
            if driver._device_id_dict[k] == self.config_dict["WeatherFlowUDP"]["devices"]:
                device_id = k
                break
  
        result = dict()
        result['device_ids'] = [device_id]
        result['types'] = ['obs_st']
        result['obs'] = (obs1, obs2, obs3, obs4, obs5, obs6, obs7, obs8, obs9, obs10)
        
        for archive_record in driver.convertREST2weewx(result):
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
                assert round(archive_record["lightning_distance"],2) == 26.0
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
                assert round(archive_record["lightning_distance"],2) == 31.00
                assert round(archive_record["supplyVoltage"],2) == 2.73
            else:
                # invalid timestamp
                assert False
                        
        pass

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()