from pymodaq_plugins_princeton_instruments.utils import Config
from pylablib.devices import PrincetonInstruments as PI

class PicamConfig :
    """
    Config object for the Picam hardware.

    Attributes
    ----------
    config : Config
        PyMoDAQ config object that contains user preferences.
    """

    def __init__(self):
        self.config = Config()
        SN_list = self.initialise_SN_list()
        self.config['PICAM']['config']['serial_numbers'] = SN_list
        if self.config['PICAM']['config']['serial_number'] == '' :
            self.config['PICAM']['config']['serial_number'] = SN_list[0]
        self.config.save()

    def initialise_SN_list(self) -> list[str] :
        """
        Probes for Picam devices and gathers their serial numbers.

        Returns
        -------
        SN_list : list
            list of serial numbers of available Picam devices.
        """
        camera_list = PI.list_cameras()
        SN_list = [tup.serial_number for tup in camera_list]
        if SN_list == [] :
            raise ImportError("No camera was detected. Please connect a camera.")
        return SN_list