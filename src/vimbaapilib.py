from vimba import *
from time import sleep
import sys
from typing import Optional

from datetime import datetime

import numpy as np
from scipy.signal import find_peaks, peak_widths

### /// 
### global variables

TS_FMT_STR = r"%Y-%m-%dT%H-%M-%S"

### /// 

def print_preamble():
    print('--- --- --- --- --- --- --- ---')
    print('--- Vimba ---------------------')
    print('--- Ivan Gadjev ---------------')
    print('--- --- --- --- --- --- --- ---')

def print_camera(cam: Camera) -> None:
    print(f'/// Camera Name: {cam.get_name()}')
    print(f'/// Camera ID: {cam.get_id()}')
    print(f'/// Interface ID: {cam.get_interface_id()}')
    
def print_usage():
    print('Usage:')
    print('    python manta-frame.py [camera_id]')
    print('    python manta-frame.py [/h] [-h]')
    print()
    print('Parameters:')
    print('    camera_id   ID of the camera to use (will use first found camera if not specified)')
    print()

def abort(reason: str, return_code: int = 1, usage: bool = False):
    print(reason + '\n')

    if usage:
        print_usage()

    sys.exit(return_code)

def parse_args() -> Optional[str]:
    args = sys.argv[1:]
    argc = len(args)

    for arg in args:
        if arg in ('/h', '-h'):
            print_usage()
            sys.exit(0)

    if argc > 1:
        abort(reason="Invalid number of arguments. Abort.", return_code=2, usage=True)

    return None if argc == 0 else args[0]

def get_camera(camera_id: Optional[str]) -> Camera:
    with Vimba.get_instance() as vimba:
        if camera_id:
            try:
                return vimba.get_camera_by_id(camera_id)

            except VimbaCameraError:
                abort(f'Failed to access Camera \'{camera_id}\'. Abort.')

        else:
            cams = vimba.get_all_cameras()
            if not cams:
                abort('No Cameras accessible. Abort.')

            return cams[0]

def setup_camera(cam: Camera):
    with cam:
        # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        try:
            cam.GVSPAdjustPacketSize.run()

            while not cam.GVSPAdjustPacketSize.is_done():
                pass

        except (AttributeError, VimbaFeatureError):
            pass

def get_frame(cam: Camera, verbose=False):
    # get the name of the camera
    camname = cam.get_name()
    pixformatstr = str(cam.get_pixel_format()) # Mono8 -> monochrome 8bit
    
    frame = cam.get_frame(timeout_ms=2000)

    now = datetime.now()
    # timestamp = datetime.timestamp(now)
    # print("timestamp = ", timestamp)
    frametsstr = datetime.strftime(now, TS_FMT_STR)
    
    if verbose:
        print(f'get frame from {camname}')
        print(f'pixel format: ' + pixformatstr)
        print(f'datetime string: {frametsstr}')

    return frame, frametsstr, pixformatstr

def save_frame(frame: Frame, savepath: str, frametsstr='now', pixformatstr='NA') -> None:
    
    print('save frame')
    if frametsstr == 'now':
        now = datetime.now()
        frametsstr = datetime.strftime(now, TS_FMT_STR)
        print('::: WARNING: No timestamp for frame was provided. File will save with timestamp at time of saving.')
    
    else:
        try:
            assert type(frametsstr) == str
            pass
            
        except AssertionError as error:
            print(error)
            frametsstr = str(frametsstr)
            print('::: WARNING: `frametsstr` was not type `str`. Conversion was made to type `str`.')

    frame_ndarray = frame.as_numpy_ndarray()
    frame_ndarray = frame_ndarray[:,:,0] # convert to 2D array, may be a problem for RGB cameras
    savefn = 'manta-frame_' + pixformatstr + '_' + frametsstr + '.npy'
    np.save(savepath+savefn, frame_ndarray)
    print(savepath+savefn)


def peak_fwhm(frame_ndarray, prominence_min=25, pixbit=8, invert=False, roi=[0, 1215, 0, 1935]):
    """
    Calculates the FWHM of the largest detected peak along the horizontal direction in the given frame.
    Built with `scipy.signal.find_peaks()` and `scipy.signal.peak_widths()`

    frame_ndarray - ndarray of the picture on which to run this routine
    prominence_min = 25. parameter fed to scipy.signal.find_peaks(). minimum height of peak above surroundings
    pixbit = 8. bits per pixel
    invert = False, invert the intesity of the picture (so that valleys appear as peaks)
    roi = [0, 1215, 0, 1935] region of interest over which to compute the mean lineout for peak detection. [row_min, row_max, col_min, col_max]. if only the horizontal line at the middle of the picture is needed: roi = [606, 607, 0, 1935]

    return
        peakwidth, peakmax, peaks_props, frame_lineout

    """
    frame_ndarray = frame_ndarray[roi[0]:roi[1], roi[2]:roi[3]]

    if invert:
        frame_ndarray = (2**pixbit - 1) - frame_ndarray

    # get the mean lineout along the horizontal pixels
    frame_lineout = np.mean(frame_ndarray, axis=0)
    # find the index locaiton of the peaks
    peaks, peaks_props = find_peaks(frame_lineout, prominence=(prominence_min, None))

    # 
    if len(peaks) > 1:
        peakmax = [ peaks[ peaks_props['prominences'].argmax() ] ]
        print('::: WARNING: Multiple peaks detected.')
        print('/// Only the most prominent peak is taken into FWHM calculation.')
        print('/// This is usually OK, but you could try increasing the prominence_min to correct for noise.')
    else:
        peakmax = peaks

    # find the peak width
    peakwidth = peak_widths(frame_lineout, peakmax, rel_height=0.5)
    
    return peakwidth, peakmax, peaks_props, frame_lineout





def main():

    print_preamble()

    lookforcameras = False

    if lookforcameras:

        # Vimba is to be used inside a with scope
        # .get_instance() inits vimba
        with Vimba.get_instance() as vimba: 
            
            cams = vimba.get_all_cameras()
            print(f'/// ')
            print(f'/// vimba found {len(cams)} camera(s)')
            print(f'/// ')
            
            for cam in cams:
                print_camera(cam)
    else:
        # change this ID if it does not match the desired camera
        # cam_id = parse_args()
        cam_id = 'DEV_000F314EED0D'
        # Vimba is to be used inside a with scope
        # .get_instance() inits vimba
        with Vimba.get_instance() as vimba:
            try:
                print(f'Attempting to get and save frame from Camera ID: {cam_id}')
                with get_camera(cam_id) as cam:
                    
                    # try to adjust the GeV packet size
                    setup_camera(cam)
                    
                    # get frame
                    frame, frameTSstr, pixfmtstr = get_frame(cam)

                    # save frame
                    SAVE_PATH = r'D:/Dropbox/RBT/4grit/laser/data/shg-test/2021-08-13/'
                    save_frame(frame, SAVE_PATH, frametsstr=frameTSstr, pixformatstr=pixfmtstr)


            finally:
                print('exit')
        
        



if __name__ == '__main__':
    main()