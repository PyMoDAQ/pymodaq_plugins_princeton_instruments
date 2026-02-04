from pylablib.devices import PrincetonInstruments as PI
from pymodaq_plugins_princeton_instruments.hardware.picamconfig import PicamConfig
from pylablib.devices.PrincetonInstruments.picam_lib import PicamError

from pymodaq_utils.logger import set_logger, get_module_name

logger = set_logger(get_module_name(__file__))

class Picam(PI.PicamCamera): 
    """
    Hardware class. Wrapper of the PicamCamera object of pylablib.

    Attributes
    ----------
    config : PicamConfig
        PicamConfig object that contains user preferences.
    SN : str
        preferred serial number
    """
    def __init__(self,*args,**kwargs):
        self.config = PicamConfig().config       
        self.SN = self.config['PICAM']['config']['serial_number']
        super().__init__(self.SN,*args,**kwargs)

    def get_camera_setting(self,setting_name : str) :
        """
        Method to get either setting or attribute from the camera.

        Parameter
        -------
        setting_name : str
            name of the attribute or setting to get

        Returns
        -------
        value
            value of the fetched attribute or setting
        """
        try :
            return self.dv[setting_name]
        except KeyError :
            try :
                return self.cav[setting_name]
            except PicamError as e :
                raise KeyError('The parameter %s is not part of the available camera parameters.',setting_name) from e

    def set_camera_setting(self,setting_name : str, value) :
        """
        Method to set either setting or attribute from the camera.

        Parameter
        -------
        setting_name : str
            name of the attribute or setting to set
        value
            value to set
        """
        try :  
            self.dv[setting_name] = value
            logger.info("The %s is set to : %s.",setting_name,value)
        except KeyError : 
            try :
                if self.get_attribute(setting_name).writable : 
                    self.cav[setting_name] = value
                    logger.info("The %s is set to : %s.",setting_name,value)
                else :
                    raise PicamError
            except PicamError : 
                logger.info('The parameter value couple : %s, %s is not valid.',setting_name, value)

               
if __name__ == '__main__' : 
    with PI.PicamCamera() as cam : 
        images = []
        cam.start_acquisition()
        for i in range(20) :
            cam.wait_for_frame()
            img = cam.read_newest_image()
            images.append(img)
            print('new frame read')
            
        print("last image")
        print(images[-1])
        print(type(images[0]))