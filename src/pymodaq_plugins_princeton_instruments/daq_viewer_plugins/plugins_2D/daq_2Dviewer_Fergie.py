import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from pymodaq_gui.parameter.utils import iter_children

from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_plugins_princeton_instruments.hardware.fergie import Fergie

from qtpy import QtWidgets, QtCore

# TODO:
# (1) change the name of the following class to DAQ_2DViewer_TheNameOfYourChoice
# (2) change the name of this file to daq_2Dviewer_TheNameOfYourChoice ("TheNameOfYourChoice" should be the SAME
#     for the class name and the file name.)
# (3) this file should then be put into the right folder, namely IN THE FOLDER OF THE PLUGIN YOU ARE DEVELOPING:
#     pymodaq_plugins_my_plugin/daq_viewer_plugins/plugins_2D
class DAQ_2DViewer_Fergie(DAQ_Viewer_base):
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
    params = comon_parameters + [
        {'title' : "ROI settings", 'name' : "roi_settings", 'type' : 'group', 'expanded' : True, 'children' : [
            {'title' : 'x origin', 'name' : 'x', 'type' : 'int', 'value' : 0},
            {'title' : 'y origin', 'name' : 'y', 'type' : 'int', 'value' : 0},
            {'title' : 'width', 'name' : 'width', 'type' : 'int', 'value' : 1024},
            {'title' : 'height', 'name' : 'height', 'type' : 'int', 'value' : 256},
            {'title' : 'x binning', 'name' : 'x_binning', 'type' : 'int', 'value' : 1},
            {'title' : 'y binning', 'name' : 'y_binning', 'type' : 'int', 'value' : 1},
        ]}
    ]

    def ini_attributes(self):
        #  TODO declare the type of the wrapper (and assign it to self.controller) you're going to use for easy
        #  autocompletion
        self.controller: Fergie = None

        # TODO declare here attributes you want/need to init with a default value

        self.x_axis = None
        self.y_axis = None
        self.running = False

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        # TODO for your custom plugin
        if param.name() in iter_children(self.settings.child('camera_settings'),[]):
            self.set_camera_setting(param)
        if param.name() in iter_children(self.settings.child('roi_settings'), []) : 
            self.set_roi_settings(param)
            self.settings.child('roi_settings')['x'] = self.controller.x
            self.settings.child('roi_settings')['y'] = self.controller.y
            self.settings.child('roi_settings')['width'] = self.controller.width
            self.settings.child('roi_settings')['height'] = self.controller.height
            self.settings.child('roi_settings')['x_binning'] = self.controller.x_binning
            self.settings.child('roi_settings')['y_binning'] = self.controller.y_binning
        # self.controller.get_setting('')
        new_frame_rate = self.controller.get_setting('frame_rate')
        self.settings.child("camera_settings")['frame_rate'] = new_frame_rate

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
        self.controller = self.ini_detector_init(slave_controller=controller, new_controller= Fergie())
        if self.is_master:
            self.controller.init_software()
            initialized = True
        else:
            self.controller = controller
            initialized = True

        self.set_axes()
        self.create_camera_settings()

        info = "Whatever info you want to log"
        return info, initialized
    
    def set_roi_settings(self,param) : 
        self.controller.__setattr__(param.name(),param.value())
    
    def create_camera_settings(self) : 
        settings_list = []
        for key in self.controller.settings.keys() :
            if self.controller.settings[key]['values_type'] == 'dict' : 
                type = "list"
                limits =  list(self.controller.settings[key]['values'].keys())
                settings_list.append({'title' : key, 'name' : key, 'type' : type, 'limits' : limits, 'readonly' : self.controller.settings[key]['read_only']   })
            elif self.controller.settings[key]['values_type'] == 'list' :
                type = "list"
                limits =  self.controller.settings[key]['values']
                settings_list.append({'title' : key, 'name' : key, 'type' : type, 'limits' : limits, 'readonly' : self.controller.settings[key]['read_only']   })
            else : 
                settings_list.append({'title' : key, 'name' : key, 'type' : self.controller.settings[key]['values_type'], 'value' : self.controller.settings[key]['default_value'], 'readonly' : self.controller.settings[key]['read_only'] })
            
        settings_group = {"title" : "Camera Settings", "name" : "camera_settings", "type" : "group", "expanded" : True, "children" : settings_list}

        self.settings.addChildren([settings_group])

    def set_camera_setting(self,param) : 
        self.controller.set_setting(setting_key=param.name(),value = param.value())
    
    def set_axes(self) : 
        data_x_axis = np.linspace(start= 0, stop = self.controller._data_shape[0], num = self.controller._data_shape[0])
        self.x_axis = Axis(data=data_x_axis, label='', units='', index=1)

        # # get the y_axis (you may want to to this also in the commit settings if y_axis may have changed
        data_y_axis = np.linspace(start= 0, stop = self.controller._data_shape[1], num = self.controller._data_shape[1]) # if possible
        self.y_axis = Axis(data=data_y_axis, label='', units='', index=0)

        self.dte_signal_temp.emit(DataToExport('Fergie',
                                               data=[DataFromPlugins(name='CCD', data=np.zeros(self.controller._data_shape),
                                                                     dim='Data2D', labels=['dat0'],
                                                                     axes=[self.x_axis, self.y_axis]), ]))

    def close(self):
        """Terminate the communication protocol"""

        self.controller.close()


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
        self.running = True
        try:

            if kwargs.get('live',False) == True :
                while self.running :  
                    data = self.controller.start()
                    if self.controller._data_shape[0] == 1 : 
                        dim = "Data1D"
                        data = data.reshape((self.controller._data_shape[1],))
                    else : 
                        dim = "Data2D"
                    self.dte_signal.emit(DataToExport('Fergie',
                                        data=[DataFromPlugins(name='CCD', data=[np.atleast_1d(
                                                data) ],
                                                                dim=dim, labels=['Munchkin']) ]))

                    QtWidgets.QApplication.processEvents()
            else:
                data = self.controller.start()
                if self.controller._data_shape[0] == 1 : 
                    dim = "Data1D"
                    data = data.reshape((self.controller._data_shape[1],))
                else : 
                    dim = "Data2D"
                self.dte_signal.emit(DataToExport('Fergie',
                                          data=[DataFromPlugins(name='CCD', data=[np.atleast_1d(data) ],
                                                                dim=dim, labels=['Munchkin']) ])) # will trigger the waitfor acquisition


        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [str(e), "log"]))
        # data_tot = self.controller.your_method_to_start_a_grab_snap()
        # self.dte_signal.emit(DataToExport('myplugin',
        #                                   data=[DataFromPlugins(name='Mock1', data=data_tot,
        #                                                         dim='Data2D', labels=['label1'],
        #                                                         x_axis=self.x_axis,
        #                                                         y_axis=self.y_axis), ]))

        ##asynchrone version (non-blocking function with callback)
        # self.controller.your_method_to_start_a_grab_snap(self.callback)
        #########################################################

    # def callback(self):
    #     """optional asynchrone method called when the detector has finished its acquisition of data"""
    #     data_tot = self.controller.your_method_to_get_data_from_buffer()
    #     self.dte_signal.emit(DataToExport('myplugin',
    #                                       data=[DataFromPlugins(name='Mock1', data=data_tot,
    #                                                             dim='Data2D', labels=['label1'],
    #                                                             x_axis=self.x_axis,
    #                                                             y_axis=self.y_axis), ]))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        ## TODO for your custom plugin
        # raise NotImplementedError  # when writing your own plugin remove this line
        # self.controller.your_method_to_stop_acquisition()  # when writing your own plugin replace this line
        self.running = False
        # #############################
        # return ''



if __name__ == '__main__':
    main(__file__)
