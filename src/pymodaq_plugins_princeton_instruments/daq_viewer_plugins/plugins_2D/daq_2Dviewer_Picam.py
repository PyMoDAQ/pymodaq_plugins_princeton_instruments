import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
import math

from qtpy import QtWidgets, QtCore

from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_plugins_princeton_instruments.hardware.picam import Picam

from pymodaq_utils.logger import set_logger, get_module_name

logger = set_logger(get_module_name(__file__))

def bin2d(array : np.ndarray, x : int,y : int) -> np.ndarray:
    """
    Summing over 2d arrays for SNR improvement.

    Parameters
    ----------
    array : np.ndarray
        input bi-dimensional data.
    x : int
        Size reduction factor of the 1-st axis
    y : int
        Size reduction factor of the 0-th axis

    Returns
    -------
    binned_arrray : np.ndarray
        Summed array with reduced size
    """
    x_bins = array.shape[1]//x
    y_bins = array.shape[0]//y
    binned_array =  array.reshape(y_bins,y,x_bins,x).sum(axis=3).sum(axis=1)
    # We want array that have shape e.g. (y,1) to reduce to (y,).
    if binned_array.shape[1] == 1 :
        binned_array = binned_array.sum(axis = 1)
    if binned_array.shape[0] == 1 :
        binned_array = binned_array.sum(axis = 0)
    return binned_array
    # https://stackoverflow.com/questions/61325586/fast-way-to-bin-a-2d-array-in-python

def get_bin_list(size) :
    """
    Produces the list of binning factors for powers of 2 shape (has a default value for other shapes)
    TODO : Improve this function to produce binning factors for any integer.

    Parameters
    ----------
    size : int
        size of the data array to be binned. e.g. data.shape[0]

    Returns
    -------
    bin_list : list[int]
        The list of binning factors

    Notes
    -----
    For example `get_bin_list(256)` will return [1,2,4,8,16,32,64,128,256]
    """
    bin_list = []
    # Either we get the power of two of the input size (integer) or the input number is not a power of two.
    power = math.log(size,2) 
    if power.is_integer() :
        for i in range(round(power + 1)) :
            bin_list.append(size//(2**i))
    else : 
        bin_list = [size,1]
    # Better to reverse for display reasons
    bin_list.reverse()
    return bin_list

class DAQ_2DViewer_Picam(DAQ_Viewer_base):
    """ 
    Instrument plugin class for a 2D viewer of the cameras that can be interfaced with the picam software.
    
    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    This plugin was tested with a PIXIS 256E and a (B)(MP)(eXcelon) but it should be compatible with any camera that can run with the picam dll.
    See : https://www.teledynevisionsolutions.com/fr-fr/products/picam-sdk-amp-driver/?model=PICAM64&vertical=tvs-princeton-instruments&segment=tvs

    This plugin was tested with PyMoDAQ 5.1.x. on Windows 11 64 bits.

    Attributes:
    -----------
    controller: Picam
        This object inherits from the PicamCamera of pylablib with almost no interface.
    x_axis : object
        2nd axis of the data, in pixel for generic use.
    y_axis : object
        1st axis of the data, in pixel for generic use.
    x_binning : int
        Summing factor on the 2nd axis of the data. The higher the binning, the lower is the length of the 2nd axis. 
    y_binning : int
        Summing factor on the 1st axis of the data. The higher the binning, the lower is the length of the 1st axis.   
    """
    live_mode_available = True
    callback_signal = QtCore.Signal(int)
    params = comon_parameters + [
            {'title' : 'x binning', 'name' : 'x_binning', 'type' : 'list', 'value' : 1, 'limits' : [1]},
            {'title' : 'y binning', 'name' : 'y_binning', 'type' : 'list', 'value' : 1, 'limits' : [1]},
            {'title' : 'exposure time (s)', 'name' : 'exposure', 'type' : 'float', 'value' : 0.1},
            {'title' : 'readout speed (MHz)', 'name' : 'adc_speed','type' : 'list',  'value' : 0.1}
    ]

    def ini_attributes(self):
        self.controller: Picam = None

        self.x_axis = None
        self.y_axis = None
        self.x_binning = 1
        self.y_binning = 1
        self._x_size = 1
        self._y_size = 1

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        if param.name() == 'x_binning' : 
            self.x_binning = param.value()
            self.set_axes()
        if param.name() == 'y_binning' : 
            self.y_binning = param.value()
            self.set_axes()
        if param.name() == 'exposure' :
            self.controller.set_camera_setting('exposure',param.value())
        if param.name() == 'adc_speed' : 
            self.controller.set_camera_setting('ADC Speed', param.value())

    def ini_detector(self, controller=None) -> tuple[str, bool]:
        """
        Detector communication and Callbacks initialization

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
        self.controller = self.ini_detector_init(slave_controller=controller, new_controller= Picam())
        if self.is_master:
            initialized = True
            self.callback = PicamCallback(self.controller)
            self.callback_thread = QtCore.QThread()
            self.callback.moveToThread(self.callback_thread)
            self.callback_thread.callback = self.callback
            self.callback_thread.start()
            self.callback_signal.connect(self.callback.readout_sequence)
            self.callback.data_sig.connect(self.emit_data)
            # The main idea behind this code is as follows :
            # The main thread that runs the DAQ2D_viewer can start and stop the acquistion at any time.
            # The second thread that runs the PicamCallback is called by the main thread on a press of the play button.
            # The second thread then loops : waits for acquisition, once ready (`wait_for_frame() == True`) sends the data to the the emit_data function.
            # If the acquisition is stopped (`wait_for_frame() == False`) then the loop stops.
        else:
            self.controller = controller
            initialized = True

        self._x_size = self.controller.get_detector_size()[0]
        self._y_size = self.controller.get_detector_size()[1]
        self.settings.child('x_binning').setLimits(get_bin_list(self.x_size))
        self.settings.child('y_binning').setLimits(get_bin_list(self.y_size))
        adc_attribute = self.controller.get_attribute('ADC Speed')
        self.settings.child('adc_speed').setLimits(adc_attribute.values)
        self.set_axes()

        info = "Whatever info you want to log"
        return info, initialized

    @property
    def y_size(self) -> int :
        return self._y_size
   
    @property
    def x_size(self) -> int :
        return self._x_size
 
    def set_axes(self) :
        """
        Set the axes for display depending on binning values. Can change the representation from 2D to 1D or 0D.
        """
        data_x_axis = np.linspace(start= 0, stop = self.x_size//self.x_binning, num = self.x_size//self.x_binning)
        data_y_axis = np.linspace(start= 0, stop = self.y_size//self.y_binning, num = self.y_size//self.y_binning)
        # Case 1 : full binning both directions -> 0D data
        if self.x_binning == self.x_size and self.y_binning == self.y_size :
            dummy_data = np.array([0.0])
        # Case 2 : full binning in the x direction -> 1D data
        elif self.x_binning == self.x_size and self.y_binning != self.y_size : 
            dummy_data = np.zeros((self.y_size//self.y_binning,))
            self.y_axis = Axis(data=data_y_axis, label='', units='', index=0)
        # Case 3 : full binning in the y direction -> 1D data
        elif self.y_binning == self.y_size and self.x_binning != self.x_size :
            dummy_data = np.zeros((self.x_size//self.x_binning,))
            self.x_axis = Axis(data=data_x_axis, label='Energy loss', units='eV', index=0)
        # Case 4 : No full binning -> 2D data
        else :
            dummy_data = np.zeros((self.y_size//self.y_binning,self.x_size//self.x_binning))
            self.y_axis = Axis(data=data_y_axis, label='', units='', index=0)
            self.x_axis = Axis(data=data_x_axis, label='Energy loss', units='eV', index=1)

        dfp = self.prepare_dfp(dummy_data)
        # Prepares the viewer
        self.dte_signal_temp.emit(DataToExport('Picam',
                                               data=dfp))
        
    def prepare_dfp (self, data : np.ndarray) -> DataFromPlugins :
        """
        Prepares DataFromPlugins for display. Chooses the right axes and data size based on the data shape.
        
        Parameters
        ----------
        data : np.ndarray
            input data. It can be any shape up to 2D.
        """ 
        if self.x_binning == self.x_size and self.y_binning == self.y_size :
            dfp = [DataFromPlugins(name = 'Picam',
                                data = data,
                                dim = 'Data0D')] 
        elif self.x_binning == self.x_size and self.y_binning != self.y_size : 
            dfp = [DataFromPlugins(name = 'Picam',
                                data = [np.atleast_1d(data)],
                                dim = 'Data1D',axes=[self.y_axis])] 
        elif self.y_binning == self.y_size and self.x_binning != self.x_size : 
            dfp = [DataFromPlugins(name = 'Picam',
                                data = [np.atleast_1d(data)],
                                dim = 'Data1D',axes=[self.x_axis])]
        else :
            dfp = [DataFromPlugins(name = 'Picam',
                                data = [np.atleast_1d(data)],
                                dim = 'Data2D',axes=[self.x_axis, self.y_axis])]
        return dfp

    def close(self):
        """Terminate the communication protocol"""
        self.controller.close()


    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Not implemented : Number of hardware averaging (if hardware averaging is possible, self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        try:
            if kwargs.get('live', False) :
                self.controller.start_acquisition()
                self.callback_signal.emit(0)
            else:
                self.controller.start_acquisition()
                self.callback_signal.emit(1)

        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [str(e), "log"]))

    def emit_data(self, data: np.ndarray) :
        """
        Updates the current displayed data.
        """
        binned_data = bin2d(data,self.x_binning, self.y_binning)
        dfp = self.prepare_dfp(binned_data)
        self.dte_signal.emit(DataToExport('Picam', data=dfp))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        self.controller.clear_acquisition()
        logger.info("Picam acquisition stopped.")


class PicamCallback(QtCore.QObject):
    """
    Callback object for the Picam camera. 

    Attributes:
    -----------
    controller: Picam
        This object inherits from the PicamCamera of pylablib with almost no interface.
    data_sig : object
        Qt signal that sends the data and start the display on the main frame
    """
    data_sig = QtCore.Signal(np.ndarray)

    def __init__(self,controller : Picam,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.controller = controller

    def readout_sequence(self, num_frames : int) :
        """
        Blocking function. Waits for data to be ready, sends a signal with collected data when they are ready.
        
        Parameters
        ----------
        num_frames : int
            number of frames to be acquired
        """
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
            for _ in range(num_frames) :
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
