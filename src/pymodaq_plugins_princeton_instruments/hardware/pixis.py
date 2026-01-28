from pylablib.devices import PrincetonInstruments as PI
from pymodaq_plugins_princeton_instruments.utils import Config

class PixisConfig :

    def __init__(self):
        self.config = Config()

class Pixis(PI.PicamCamera) : 
    def __init__(self,*args,**kwargs):
        self.config = PixisConfig().config
        self.SN = self.config['PIXIS']['config']['serial_number']
        super().__init__(self.SN)
    
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