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


    def testName(self):
        driver = user.weatherflowudp.WeatherFlowUDPDriver(self.config_dict)
        for archive_record in driver.genStartupRecords(int(time.time())-900):
            print(archive_record)
        pass


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()