pymodaq_plugins_princeton_instruments
#####################################

.. image:: https://github.com/PyMoDAQ/pymodaq_plugins_princeton_instruments/workflows/Upload%20Python%20Package/badge.svg
   :target: https://github.com/PyMoDAQ/pymodaq_plugins_princeton_instruments
   :alt: Publication Status

.. image:: https://github.com/PyMoDAQ/pymodaq_plugins_princeton_instruments/actions/workflows/Test.yml/badge.svg
    :target: https://github.com/PyMoDAQ/pymodaq_plugins_princeton_instruments/actions/workflows/Test.yml

Authors
=======

* Adrien Teurtrie  (adrien.teurtrie@cemes.fr)

Instruments
===========

Below is the list of instruments included in this plugin

Viewer2D
++++++++

* **Fergie**: control of the Fergie spectrometer and its camera. It works through communication with the lightfield software. 
* **Picam**: control of 2D detectors that can be controlled with the Picam.dll of Teledyne. 

Installation instructions
=========================

* PyMoDAQ 5.1.x
* Windows 11 64 bits
* For the Fergie, installing the LightField software of Teledyne is required : https://www.teledynevisionsolutions.com/en-au/products/lightfield/?model=LF&vertical=tvs-princeton-instruments&segment=tvs (tested with an outdated licence.)
* For the Picam, installing the Picam software of Teledyne is required : https://www.teledynevisionsolutions.com/en-au/products/picam-sdk-amp-driver/?model=PICAM64&vertical=tvs-princeton-instruments&segment=tvs

Work to be done
===============

* Create a DAQMove to control the wavelength of the Fergie. 
* Test multiple Picam cameras working together.
* Improve the code and documentation of the Fergie DAQ2D_Viewer
* Implement ROIs for the Picam