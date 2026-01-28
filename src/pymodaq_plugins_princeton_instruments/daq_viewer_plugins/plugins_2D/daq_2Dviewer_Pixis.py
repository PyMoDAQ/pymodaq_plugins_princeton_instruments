import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from pymodaq_gui.parameter.utils import iter_children

from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_plugins_princeton_instruments.hardware.pixis import Pixis
from pylablib.devices import PrincetonInstruments as PI

from pymodaq_utils.logger import set_logger, get_module_name

from qtpy import QtWidgets, QtCore

logger = set_logger(get_module_name(__file__))

def bin2d(array, x,y) :
    x_bins = array.shape[1]//x
    y_bins = array.shape[0]//y
    binned_array =  array.reshape(y_bins,y,x_bins,x).sum(axis=3).sum(axis=1)
    if binned_array.shape[1] == 1 :
        binned_array = binned_array.sum(axis = 1)
    if binned_array.shape[0] == 1 :
        binned_array = binned_array.sum(axis = 0)
    return binned_array
    # https://stackoverflow.com/questions/61325586/fast-way-to-bin-a-2d-array-in-python

# TODO:
# (1) change the name of the following class to DAQ_2DViewer_TheNameOfYourChoice
# (2) change the name of this file to daq_2Dviewer_TheNameOfYourChoice ("TheNameOfYourChoice" should be the SAME
#     for the class name and the file name.)
# (3) this file should then be put into the right folder, namely IN THE FOLDER OF THE PLUGIN YOU ARE DEVELOPING:
#     pymodaq_plugins_my_plugin/daq_viewer_plugins/plugins_2D
class DAQ_2DViewer_Pixis(DAQ_Viewer_base):
    """ Instrument plugin class for a 2D viewer.
    
    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    TODO Complete the docstring of your plugin with:
        * The set of instruments that should be compatible with this instrument plugin.
        * With which instrument it has actually been tested.
        * The version of PyMoDAQ during the test.
        * The version of the operating system.
        * Installation instructions: what manufacturer’s drivers should be installed to make it run?

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware, in general a python wrapper around the
         hardware library.
         
    # TODO add your particular attributes here if any

    """
    live_mode_available = True
    callback_signal = QtCore.Signal(int)
    params = comon_parameters + [
            {'title' : 'x binning', 'name' : 'x_binning', 'type' : 'list', 'value' : 1, 'limits' : [1,2,4,8,16,32,64,128,256,512,1024]},
            {'title' : 'y binning', 'name' : 'y_binning', 'type' : 'list', 'value' : 1, 'limits' : [1,2,4,8,16,32,64,128,256]},
            {'title' : 'dispersion (eV/ch)', 'name' : 'dispersion', 'type' : 'float', 'value' : 1.0},
            {'title' : 'energy offet (eV)', 'name' : 'offset', 'type' : 'float', 'value' : 0.0},
            {'title' : 'exposure time', 'name' : 'exposure', 'type' : 'float', 'value' : 0.1}
    ]

    def ini_attributes(self):
        #  TODO declare the type of the wrapper (and assign it to self.controller) you're going to use for easy
        #  autocompletion
        self.controller: Pixis = None

        # TODO declare here attributes you want/need to init with a default value

        self.x_axis = None
        self.y_axis = None
        self.x_binning = 1
        self.y_binning = 1
        self.dispersion = 1.0
        self.offset = 0.0
        # self.exposure = 0.1

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        # TODO for your custom plugin
        if param.name() == 'x_binning' : 
            self.x_binning = param.value()
            self.set_axes()
        if param.name() == 'y_binning' : 
            self.y_binning = param.value()
            self.set_axes()
        if param.name() == 'dispersion' : 
            self.dispersion = param.value()
            self.set_axes()
        if param.name() == 'offset' : 
            self.offset = param.value()
            self.set_axes()
        if param.name() == 'exposure' :
            # self.exposure = param.value()
            # self.callback.set_exposure(param.value)
            self.set_camera_setting('exposure',param.value())

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one actuator/detector by controller
            (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """
        self.controller = self.ini_detector_init(slave_controller=controller, new_controller= Pixis())
        if self.is_master:
            initialized = True
            # CT02. An object (called callback), is instanciated.
            self.callback = PixisCallback(self.controller)
            # CT03. A thread object is created (callback_thread)
            self.callback_thread = QtCore.QThread()
            # CT04. The thread object is made ready to be executed parallel to the main thread
            self.callback.moveToThread(self.callback_thread)
            # CT05. The function to be called by the thread is the callback object
            self.callback_thread.callback = self.callback
            # CT06. We make the thread ready to execute
            self.callback_thread.start()
            # CT07. We connect the signal to the execution of data read-out from the detector
            self.callback_signal.connect(self.callback.readout_sequence)
            # CT08. We connect the signal of the callback to the execution of PyMoDAQ GUI to display data.
            self.callback.data_sig.connect(self.emit_data)
        else:
            self.controller = controller
            initialized = True

        self.set_axes()

        info = "Whatever info you want to log"
        return info, initialized
    
    def get_camera_setting(self,setting_name : str) : 
        all_settings = self.controller.get_settings()
        return all_settings[setting_name]

    def set_camera_setting(self,setting_name : str, value) : 
        self.controller.dv[setting_name] = value
        logger.info(f"The {setting_name} is set to : {value}.")
  
    def set_axes(self) : 
        data_x_axis = np.linspace(start= self.offset, stop = self.dispersion*(1024//self.x_binning)+self.offset, num = 1024//self.x_binning)
        data_y_axis = np.linspace(start= 0, stop = 256//self.y_binning, num = 256//self.y_binning)
        if self.x_binning == 1024 and self.y_binning == 256 :
            dummy_data = np.array(0.0)
        elif self.x_binning == 1024 and not(self.y_binning == 256) : 
            dummy_data = np.zeros((256//self.y_binning,))
            self.y_axis = Axis(data=data_y_axis, label='', units='', index=0)
        elif self.y_binning == 256 and not(self.x_binning == 1024) :
            dummy_data = np.zeros((1024//self.x_binning,))
            self.x_axis = Axis(data=data_x_axis, label='Energy loss', units='eV', index=0)
        else :
            dummy_data = np.zeros((256//self.y_binning,1024//self.x_binning))
            self.y_axis = Axis(data=data_y_axis, label='', units='', index=0)
            self.x_axis = Axis(data=data_x_axis, label='Energy loss', units='eV', index=1)
        # # get the y_axis (you may want to to this also in the commit settings if y_axis may have changed
         # if possible

        dtp = self.prepare_dwa(dummy_data)

        self.dte_signal_temp.emit(DataToExport('Pixis',
                                               data=dtp))
        
    def prepare_dwa (self, data) : 
        if self.x_binning == 1024 and self.y_binning == 256 :
            dtp = [DataFromPlugins(name = 'Pixis',
                                data = data,
                                dim = 'Data0D')] 
        elif self.x_binning == 1024 and not(self.y_binning == 256) : 
            dtp = [DataFromPlugins(name = 'Pixis',
                                data = [np.atleast_1d(data)],
                                dim = 'Data1D',axes=[self.y_axis])] 
        elif self.y_binning == 256 and not(self.x_binning == 1024) : 
            dtp = [DataFromPlugins(name = 'Pixis',
                                data = [np.atleast_1d(data)],
                                dim = 'Data1D',axes=[self.x_axis])]
        else :
            dtp = [DataFromPlugins(name = 'Pixis',
                                data = [np.atleast_1d(data)],
                                dim = 'Data2D',axes=[self.x_axis, self.y_axis])]
        return dtp

    def close(self):
        """Terminate the communication protocol"""
        pass
        # self.controller.close()


    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible, self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        ## TODO for your custom plugin: you should choose EITHER the synchrone or the asynchrone version following

        ##synchrone version (blocking function)
        try:
            if kwargs.get('live',False) == True :
                self.controller.start_acquisition()
                self.callback_signal.emit(0)
            else:
                self.controller.start_acquisition()
                self.callback_signal.emit(1)

        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [str(e), "log"]))

    def emit_data(self, data : np.ndarray) :
        binned_data = bin2d(data,self.x_binning,self.y_binning)
        dtp = self.prepare_dwa(binned_data)
        self.dte_signal.emit(DataToExport('Pixis',
                                            data=dtp))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        ## TODO for your custom plugin
        # raise NotImplementedError  # when writing your own plugin remove this line
        # self.controller.your_method_to_stop_acquisition()  # when writing your own plugin replace this line
        
        self.controller.clear_acquisition()
        # logger.info("Pixis acquisition stopped.")
        # #############################
        # return ''

class PixisCallback(QtCore.QObject):
    data_sig = QtCore.Signal(np.ndarray)

    def __init__(self,controller,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.controller = controller

    def readout_sequence(self, num_frames) :
        if num_frames == 0 : 
            while True :
                try :
                    if self.controller.wait_for_frame() : 
                        image = self.controller.read_newest_image()
                        self.data_sig.emit(image)
                    else :
                        logger.info("Secondary thread readout sequence stopped.")
                        break
                except TypeError :
                    break
        else : 
            for frame in range(num_frames) : 
                try :
                    if self.controller.wait_for_frame() : 
                        image = self.controller.read_newest_image()
                        self.data_sig.emit(image)
                    else :
                        logger.info("Secondary thread readout sequence stopped.")
                        break
                except TypeError :
                    break

if __name__ == '__main__':
    main(__file__)
