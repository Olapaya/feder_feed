#from sensor import GroveUltrasonicRanger
import seeed_dht
from picamera2 import Picamera2, MappedArray, Preview
from picamera2.outputs import FileOutput
import os
import numpy as np
import time
from datetime import datetime
import RPi.GPIO as GPIO
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import code
from skimage.metrics import structural_similarity as ssim
import cv2

def main(args):
    """
    Detect Bird from PiCamera2 images
    This script first takes a reference image
    Every second a new image is taken and the SSIM (Structural Similarity Index) score is calculated to detect changes between image and reference.
    A detection is triggered if the SSIM score if below a predefined threshold. In this case 3 images are stored in the image folder, the filename, humditiy, temperature and time is added to a detection file
    Every 30s a new reference image is taken.
    
    The measurements are using the LowRes Camera stream, which is in YUV420p colorspace. This is first converted to RGB and then GRAY to calculate SSIM for processor efficiency.
    Detection images are taken in HighResolution RGB

    Parameters
    ----------
    gpio: int, Default: 26
        GPIOPin for DHT sensor
    save: bool, optional, Default: False
        Save detection images to imagepath
    show: bool, optional, Default: False
        Show image preview
    score: float Default: 95
        SSIM score threshold for detection. Should be in range 0-100 (100% means similiar image and reference)
    zoom: float. Default: 40
        Picture zoom. Should be in range 0-100%
    help: bool, Default: False
        Show help
    path: str, Default: photos/
        Imagedirectory
    """

#Set initial values
    GPIOpin=26
    takepic=False
    minscore=95
    zoom=45
    showhelp=False
    showpreview=False
    imagepath='./photos/'
    
    #Parse commandline parameters
    for arg in args:
        if 'save' in arg.lower(): takepic=True
        if 'show' in arg.lower(): showpreview=True
        if 'score' in arg.lower(): minscore=float(arg.split('=')[1])
        if 'zoom' in arg.lower(): zoom=int(arg.split('=')[1])
        if 'help' in arg.lower(): showhelp=True
        if 'path' in arg.lower(): imagepath=str(arg.split('=')[1])
        if 'gpio' in arg.lower(): GPIOpin=int(arg.split('=')[1])


    if showhelp:
        print('% Call is: python detect_freaks.py save score=95 zoom=45')
        print('%  Options:                                               %')
        print('%  --------                                               %')
        print('%  gpio=26: GPIOpin for sensor. Default: 26               %')
        print('%  save: Save images to disk                              %')
        print('%  show: Show image preview                               %')
        print('%  score=80: SSIM score threshold. Default: 80            %')
        print('%  zoom=XX: Image zoom level. Default: 0                  %')
        print('%  path=./photos/: Image zoom level. Default: ./photos/   %')
        print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
        return
    
    #Initialize statistic plot x-axis format
    formatter = mdates.DateFormatter(('%H:%M'))

    #Check if image path exists, if not generate
    if (os.path.isdir(imagepath)==False): os.makedirs(imagepath)

    #Initialize Sensor and Camera
    picam = Picamera2()
    picam.configure(picam.create_still_configuration(lores={"size": (320, 240)}))
    picam.start()
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%  Freak detection algorithm v2.0                         %')
    print('%  Author: S. Schindler, R. Wolfert, M. Chahabadi         %')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    time.sleep(1)
    #Initialize scene setup
    print('Initializing...')
    print('---------------')
    picam.set_controls({"AfMode": 0, "LensPosition": 1.8})

    #Set Camera zoom
    if zoom > 0:
        print('Zooming in by '+str(zoom)+'%')
        sizeorig = picam.capture_metadata()['ScalerCrop'][2:]
        full_res = picam.camera_properties['PixelArraySize']
        size = [int(s * (1.-zoom/100.)) for s in sizeorig]
        offset = [(r - s) // 2 for r, s in zip(full_res, size)]
        picam.set_controls({"ScalerCrop": offset + size})
        time.sleep(1)
        
    

    try:
        print('DHT sensor found')
        dhtsensor=seeed_dht.DHT("11", GPIOpin)
        humi, temp = dhtsensor.read()
        usedht=True
        print('Actual humidity: '+'%.2f' %humi+'%')
        print('Actual temperature: '+'%.2f' %temp+'°C')
    except:
        usedht=False
    #Take first image to apply zoom
    image = picam.capture_image()
    if showpreview: image.show()
    #code.interact(local=locals()) 
    #Take reference image (low-res) and convert from YUV420 to GRAY)
    #refimage = picam.capture_array("main")
    refimage= cv2.cvtColor(picam.capture_array("lores"), cv2.COLOR_YUV420p2RGB)

        


    #Initialize runtime variables and arrays
    count=0 #Number of detections
    countsec=0 #Count seconds after start

    timestamp=[] #detection timestamp array
    times=[]     #detection time array
    filenames=[] #detection image filename array


    if usedht:
        humidarr=[] #distance measurement array (for statistics)
        temparr=[] #distance measurement array (for statistics)
        humidity=[]  #detection humidity array
        temperature=[] #detection temperature array
    msearr=[] #mse measurement array (for statistics)
    msetime=[] #mse measurement time array (for statistics)
    scorearr=[]#SSIM score array (for statistics)

    #Open detection file
    print('Saving detections to: Detections_'+datetime.now().strftime("%Y%m%d")+'.txt')
    


    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%% Waiting for detection...    %%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')


    try:
        while True:
            
            
            #Take lowres image and convert to RGB
            image= cv2.cvtColor(picam.capture_array("lores"), cv2.COLOR_YUV420p2RGB)
            if np.mean(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)) <50:
            #if int(datetime.now().strftime('%H')) >16 or :
                print('Too dark to detect birds')
                break
            #Calculate SSIM score and MSE between image and reference (Using Gray image)
            score, diff = ssim(cv2.cvtColor(refimage, cv2.COLOR_RGB2GRAY), cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), full=True)
            #Calculate MSE between image and reference (Using Gray image)
            mse=np.mean((refimage-image)**2)
            
            #Add to statistics arrays
            msearr.append(mse)
            scorearr.append(score* 100)
            msetime.append(datetime.now())
            
            # Measure Temperature and Humidity
            if usedht:
                humi, temp = dhtsensor.read()
                humidarr.append(humi)
                temparr.append(temp)
                
            # Is MSE exceeds threshold, we have a detection!
            #if mse >minmse:
            #IF SSIM score is lower than threshold, we have a detection! 
                
            if score* 100 < minscore:
                times.append(datetime.now()) #Save time
                timestamp.append(times[count].strftime("%Y-%m-%dT%H-%M-%S")) #Save timestamp
                print('DETECTION! '+timestamp[count]+' MSE: '+str(mse)+' Similarity: {:.3f}%'.format(score * 100))
                
                if takepic: 
                    filenames.append('capture_'+str(timestamp[count])+'.jpg')
                    print('Taking picture. Saving to: '+filenames[count])
                    picam.capture_file(imagepath+filenames[count])
                else:
                    filenames.append('')
                with open('Detections_'+datetime.now().strftime("%Y%m%d")+'.txt','a') as f:
                    f.write(timestamp[count]+' '+'%.2f' % humidarr[count]+' '+'%.2f' % temparr[count]+' '+'%.2f' % scorearr[count]+' '+filenames[count]+'\n')
                if usedht:
                    humidity.append(humi) #Save humidity
                    temperature.append(temp) #Save temperature


                #If keyword is set, show detection image
                if showpreview: picam.capture_image().show()
                    
                count+=1
                #Take 2 additional pictures
                if takepic: 
                    picam.capture_file(imagepath+'capture_'+datetime.now().strftime("%Y-%m-%dT%H-%M-%S.jpg"))
                    time.sleep(1)
                    picam.capture_file(imagepath+'capture_'+datetime.now().strftime("%Y-%m-%dT%H-%M-%S.jpg"))
                    
                #After detection wait if bird is still there. Wait for 10s, perform new measurement and wait longer if there is still a detection
                time.sleep(10)

                print('Ready for next detections...')
                print('----------------------------')
            time.sleep(1)
            countsec+=1
            
            #Take new reference measurement every 30s
            if countsec % 30 == 0: 
                #refimage = picam.capture_array("main")
                refimage= cv2.cvtColor(picam.capture_array("lores"), cv2.COLOR_YUV420p2RGB)

                
                #Make MSE statistics plot
                fig, (ax1,ax2) = plt.subplots(2,1)
                ax1.plot(msetime,msearr,'k.')
                #ax1.axhline(minmse,color='k',linestyle='--')
                ax1.set_xlabel('Time')
                ax1.set_ylabel('MSE')
                ax1.set_ylim([0,100])
                ax1.xaxis.set_major_formatter(formatter)
                
                ax12 = ax1.twinx()
                ax12.set_ylabel('SSIM',color='tab:blue')
                ax12.tick_params(axis='y', labelcolor='tab:blue')
                ax12.plot(msetime, scorearr, 'b.')
                ax12.axhline(minscore,color='b',linestyle='--')
                if usedht:
                    color = 'tab:red'
                    ax2.set_xlabel('Time')
                    ax2.set_ylabel('Temperature', color=color)
                    ax2.plot(msetime, temparr, 'r.')
                    ax2.tick_params(axis='y', labelcolor=color)
                    ax3 = ax2.twinx()  # instantiate a second axes that shares the same x-axis
                    color = 'tab:blue'
                    ax3.set_ylabel('Humidity', color=color)  # we already handled the x-label with ax1
                    ax3.plot(msetime, humidarr, 'b.')
                    ax3.tick_params(axis='y', labelcolor=color)
                    ax2.xaxis.set_major_formatter(formatter)

                fig.savefig('MSEStatistics_'+datetime.now().strftime("%Y%m%d")+'.png')
                plt.close()
            
    #If code is interrupted clean up        
    except KeyboardInterrupt: 
        GPIO.cleanup()
        picam.close()
        
    print(count,'detections!')
    #If there are detections, store detection info into file
    #Make statistic plots (i.e. humidity and temperature as function of time
    if count>0:
        
        
        if not usedht:
            temperature=np.ones(count)
            humidity=np.ones(count)
        fig, ax1 = plt.subplots()
        color = 'tab:red'
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Temperature', color=color)
        ax1.plot(times, temperature, color=color,marker='.')
        ax1.tick_params(axis='y', labelcolor=color)

        ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
        color = 'tab:blue'
        ax2.set_ylabel('Humidity', color=color)  # we already handled the x-label with ax1
        ax2.plot(times, humidity, color=color,marker='.')
        ax2.tick_params(axis='y', labelcolor=color)
        ax1.xaxis.set_major_formatter(formatter)
        
        fig.savefig('Statistics_'+datetime.now().strftime("%Y%m%d")+'.png')
        
    time.sleep(5)
    return

if __name__ == '__main__':
    sys.exit(main(sys.argv))
