# Import the .NET class library
import clr
from dataclasses import dataclass, make_dataclass, field
# from enum import Enum
# Import python sys module
import sys

# Import os module
import os

# Import System.IO for saving and opening files
from System.IO import *

# Import c compatible List and String
from System import *
from System.Collections.Generic import List
from System.Runtime.InteropServices import Marshal
from System.Runtime.InteropServices import GCHandle, GCHandleType
import ctypes

# Add needed dll references
sys.path.append(os.environ['LIGHTFIELD_ROOT'])
sys.path.append(os.environ['LIGHTFIELD_ROOT']+"\\AddInViews")
clr.AddReference('PrincetonInstruments.LightFieldViewV5')
clr.AddReference('PrincetonInstruments.LightField.AutomationV5')
clr.AddReference('PrincetonInstruments.LightFieldAddInSupportServices')

# PI imports
from PrincetonInstruments.LightField.Automation import Automation
from PrincetonInstruments.LightField.AddIns import ExperimentSettings, CameraSettings, ImageDataFormat, DeviceType, RegionOfInterest

from pymodaq_plugins_princeton_instruments.utils import Config
from pathlib import Path
import re
import json
from pymodaq_utils.logger import set_logger, get_module_name
import numpy as np
from typing import Dict, Any, ClassVar

logger = set_logger(get_module_name(__file__))

# settings_path = Path(__file__).parent / Path('fergie_settings.json')

class FergieConfig :

    def __init__(self):
        self.config = Config()
        self.available_exps = self.list_experiments()

    def list_experiments(self) : 
        folder_path = Path(self.config['FERGIE']['config']['exp_folder'])
        all_files = os.listdir(folder_path)
        selected_files = []
        for file in all_files : 
            m = re.match(r"(.*)(\." + 'lfe' + r")", file)
            if m : 
                selected_files.append(Path(folder_path) / Path(file))

        return selected_files

class Fergie : 
    def __init__(self):
        self.config = FergieConfig()
        self._experiment_name = self.config.available_exps[0]
        self.auto = None
        self.experiment = None
        self.device_name_list = []
        self._camera = None
        # self.roi = None
        self.create_settings()
        self._x = 0
        self._y = 0
        self._width = 1024
        self._height = 256
        self._x_binning = 1
        self._y_binning = 1
        self._data_shape = (256,1024)

    def create_settings(self) : 
        with open(self.config.config['FERGIE']['config']['settings_file']) as f :
            settings_dict = json.load(f) 
            
        # fields = [(k, ClassVar[Dict[str,Any]], field(default= settings_dict[k])) for k in settings_dict.keys()]
        # FergieSettings = make_dataclass('FergieSettings',fields)
        self.settings = settings_dict

    def init_software(self) : 
        self.auto = self.load_auto(self.experiment_name)
        self.experiment = self.auto.LightFieldApplication.get_Experiment()
        if not(self.device_found()) : 
            raise ConnectionError("Camera not found. Please add a camera and try again.")
        self.device_name_list = self.list_devices()
        self.camera = (self.config['FERGIE']['config']['name'],self.config['FERGIE']['config']['serial_number'])
        self.experiment.SetCustomRegions([RegionOfInterest(0,0,1024,256,1,1)])
        # self.roi = self.experiment.FullSensorRegion

    def device_found(self):
        # Find connected device
        for device in self.experiment.ExperimentDevices:
            if (device.Type == DeviceType.Camera):
                return True
        
        # If connected device is not a camera inform the user
        return False

    def load_auto(self, experiment) : 
        list1 = List[String]()
        list1.Add(f"/{experiment}")
        return Automation(True, List[String](list1))

    def list_devices(self) :
        dnl = []
        for device in self.experiment.ExperimentDevices : 
            dnl.append((device.Model,device.SerialNumber))
        return dnl
    
    def get_command(self, lf_string) : 
        return self.experiment.GetValue(lf_string)
    
    def set_command(self, lf_string, value) : 
        return self.experiment.SetValue(lf_string, value)
    
    def get_setting(self, setting_key) : 
        return self.get_command(self.settings[setting_key]['lf_string'])
    
    def set_setting(self, setting_key, value) : 
        if self.settings[setting_key]['read_only'] : 
            logger.info("This variable is read-only, impossible to set.")
        else :
            if self.settings[setting_key]['values'] == 'None' : 
                if self.settings[setting_key]['type'] == 'int' : 
                    c_value = Int32(value)
                elif self.settings[setting_key]['type'] == 'float' :
                    c_value = Double(value) 
                else : 
                    raise ValueError('Type not understood.') 
            elif (value in self.settings[setting_key]['values']) :
                if self.settings[setting_key]['values_type'] == 'dict' : 
                    input_val = self.settings[setting_key]['values'][value]
                # elif value < self.settings[setting_key].get("min") : 
                #     input_val = self.settings[setting_key]["min"]
                # elif value > self.settings[setting_key].get("max"): 
                #     input_val = self.settings[setting_key]['max']
                else :
                    input_val = value
                if self.settings[setting_key]['type'] == 'int' : 
                    c_value = Int32(input_val)
                elif self.settings[setting_key]['type'] == 'float' :
                    c_value = Double(input_val) 
                else : 
                    raise ValueError('Type not understood.')
            self.set_command(self.settings[setting_key]['lf_string'],
                                     c_value)
                
    def start(self) : 
        self.set_command('numframes', Int32(1))
        dataset = self.experiment.Capture(1)
        image_data = dataset.GetFrame(0, 0).GetData()
        image_frame = dataset.GetFrame(0, 0)
        array = self.convert_buffer(image_data, image_frame.Format)
        return array


    def close(self) :
        if self.auto is None : 
            logger.info("Lightfield was not initialized. Closing did nothing.")
        else : 
            self.auto.Dispose()

    def convert_buffer(self,net_array, image_format):
        src_hndl = GCHandle.Alloc(net_array, GCHandleType.Pinned)
        try:
            src_ptr = src_hndl.AddrOfPinnedObject().ToInt64()

            # Possible data types returned from acquisition
            if (image_format==ImageDataFormat.MonochromeUnsigned16):
                buf_type = ctypes.c_ushort*len(net_array)
            elif (image_format==ImageDataFormat.MonochromeUnsigned32):
                buf_type = ctypes.c_uint*len(net_array)
            elif (image_format==ImageDataFormat.MonochromeFloating32):
                buf_type = ctypes.c_float*len(net_array)
                        
            cbuf = buf_type.from_address(src_ptr)
            resultArray = np.frombuffer(cbuf, dtype=cbuf._type_)

        # Free the handle 
        finally:        
            if src_hndl.IsAllocated: src_hndl.Free()
            
        # Make a copy of the buffer
        return resultArray.reshape(self._data_shape)

    @property
    def experiment_name(self) : 
        return self._experiment_name
    
    @experiment_name.setter
    def experiment_name(self, value : str) : 
        if value in self.config.available_exps :
            self._experiment_name = value
        else : 
            logger.info(f"The experiment {value} does not exist. Please choose among avalaible choices : {self.config.available_exps}.")
            logger.info(f"The current experiment is {self._experiment_name}.")

    @property
    def camera(self) : 
        if self._camera is None : 
            raise ValueError('Please choose a camera.')
        return self._camera
    
    @camera.setter
    def camera(self,value : tuple[str]) : 
        if value in self.device_name_list : 
            for device in self.experiment.ExperimentDevices :
                if device.Type == DeviceType.Camera and device.Model == value[0] and device.SerialNumber == value[1] :
                    self._camera = device

        else : 
            logger.info(f'The device named {value[0]} with SN {value[1]} does not exist.')
            logger.info(f'Please choose among avalaible choices : {self.device_name_list}')
            logger.info(f"The current device is {self._camera}.")

    @property
    def x(self) : 
        return self._x
    
    @x.setter
    def x(self, value : int) :
        wl_value = within_limits(value,0,1024-self._width)
        self._x = wl_value
        # self._width += - wl_value 
        self._x_binning = find_closest_divisor(self._width,self._x_binning)
        roi = RegionOfInterest(self._x,
                               self._y,
                               self._width,
                               self._height,
                               self._x_binning,
                               self._y_binning)
        self.experiment.SetCustomRegions([roi])
        self._data_shape = (self._height//self._y_binning,self._width//self._x_binning)

    @property
    def y(self) : 
        return self._y
    
    @y.setter
    def y(self, value : int) :
        wl_value = within_limits(value,0,256-self._height)
        self._y = wl_value
        # self._height += - wl_value 
        self._y_binning = find_closest_divisor(self._height,self._y_binning)
        roi = RegionOfInterest(self._x,
                               self._y,
                               self._width,
                               self._height,
                               self._x_binning,
                               self._y_binning)
        self.experiment.SetCustomRegions([roi])
        self._data_shape = (self._height//self._y_binning,self._width//self._x_binning)

    @property
    def width(self) : 
        return self._width
    
    @width.setter
    def width(self, value : int) :
        wl_value = within_limits(value,1,1024-self._x)
        self._width = wl_value 
        self._x_binning = find_closest_divisor(self._width,self._x_binning)
        roi = RegionOfInterest(self._x,
                               self._y,
                               self._width,
                               self._height,
                               self._x_binning,
                               self._y_binning)
        self.experiment.SetCustomRegions([roi])
        self._data_shape = (self._height//self._y_binning,self._width//self._x_binning)

    @property
    def height(self) : 
        return self._height
    
    @height.setter
    def height(self, value : int) :
        wl_value = within_limits(value,1,256-self._y)
        self._width = wl_value 
        self._y_binning = find_closest_divisor(self._height,self._y_binning)
        roi = RegionOfInterest(self._x,
                               self._y,
                               self._width,
                               self._height,
                               self._x_binning,
                               self._y_binning)
        self.experiment.SetCustomRegions([roi])
        self._data_shape = (self._height//self._y_binning,self._width//self._x_binning)

    @property
    def x_binning(self) : 
        return self._x_binning
    
    @x_binning.setter
    def x_binning(self, value : int) :
        wl_value = within_limits(value,1,self._width)
        self._x_binning = find_closest_divisor(self._width,wl_value)
        roi = RegionOfInterest(self._x,
                               self._y,
                               self._width,
                               self._height,
                               self._x_binning,
                               self._y_binning)
        self.experiment.SetCustomRegions([roi])
        self._data_shape = (self._height//self._y_binning,self._width//self._x_binning)

    @property
    def y_binning(self) : 
        return self._y_binning
    
    @y_binning.setter
    def y_binning(self, value : int) :
        wl_value = within_limits(value,1,self._height)
        self._y_binning = find_closest_divisor(self._height,wl_value)
        roi = RegionOfInterest(self._x,
                               self._y,
                               self._width,
                               self._height,
                               self._x_binning,
                               self._y_binning)
        self.experiment.SetCustomRegions([roi])
        self._data_shape = (self._height//self._y_binning,self._width//self._x_binning)


def within_limits(val, lower=None, upper=None):
    """ limit a value to be within a minimum and maximum
    """
    if not(lower is None) and not(upper is None) :
        assert upper >= lower, "input range given is impossible"
    if not(lower is None):
        val = max(lower, val)
    if not(upper is None):
        val = min(val, upper)
    return val

def find_closest_divisor(w, b):
    # Ensure w is positive
    if w == 0:
        raise ValueError("w must be a non-zero integer")

    # Handle the case where b is 0 separately
    if b == 0:
        return abs(w)

    # Find all divisors of w
    divisors = set()
    for i in range(1, int(abs(w)**0.5) + 1):
        if w % i == 0:
            divisors.add(i)
            divisors.add(w // i)

    # Find the divisor closest to b
    closest_divisor = None
    min_distance = float('inf')

    for divisor in divisors:
        distance = abs(divisor - b)
        if distance < min_distance:
            min_distance = distance
            closest_divisor = divisor
        elif distance == min_distance:
            # If there's a tie, choose the smaller divisor
            if divisor < closest_divisor:
                closest_divisor = divisor

    return closest_divisor

if __name__ == '__main__' : 
    f = Fergie()
    try :
        f.init_software() 
        # f.print_devices()
        import time
        time.sleep(1)
        f.start()
        f.y_binning = 256
        f.start()
        f.width = 112
        f.height = 110
        f.x = 780
        f.y = 34
        print(f.x_binning)
        print(f.y_binning)
        print(f.get_setting('gain'))
        print(f.get_setting('adc_speed'))
        print(f.get_setting('shift_rate'))
        print(f.get_setting('exposure_time'))
        print(f.get_setting('readout_mode'))
        f.start()
        f.close()
    finally : 
        f.close()
