# -*- coding: utf-8 -*-
"""
Created on Mon Apr  9 11:39:21 2018

@author: Jacob
"""

# script used to open the LIDAR shutter at specified times or SZAs of day
# THANKS to cmoriarty who commented on the issue on github (https://github.com/qpit/thorlabs_apt/issues/3)
# You will need to install ftd2xx and pyephem if you haven't already
# pip install ftd2xx
# conda install -c astropy pyephem
# More byte level commands are in the "Thorlabs APT Controllers Host-Controller Communications Protocol" documentation
# (https://www.thorlabs.com/software/apt/APT_Communications_Protocol_Rev_15.pdf)
# NOTE: I don't currently have a good way to exit this program gracefully. It gets "stuck"
# in sleep mode. So I guess just close down python
# used this website to find current SZA when testing: http://suncalc.net/#/43.6612,-79.3977,18/2018.04.10/12:54
# There are 2 options to define sunrise/sunset, based on SZA or computer time (uot_sza_srise, or comp_srss)
# One is used in the main "while" loop below


#%% import some modules
import ephem
import numpy as np
import datetime as dt
import time
#import sys
#sys.path.insert(0, 'C:/Users/Jacob_2/Documents/Python/auto_shutter/thorlabs_apt/thorlabs_apt')
import ftd2xx
import ftd2xx.defines as constants


#%% testing
#import thorlabs_apt as apt #for position detection
#dvc_srls=apt.list_available_devices() #save device serial numbers
##srl_num = dvc_srls[0][1] #serial number for device of interest (37872128)
#srl_num = 37872128
#motor = apt.Motor(srl_num)

#%% define common commands
# Raw byte commands for "MGMSG_MOT_MOVE_JOG".
#opn_position = b"\x6A\x04\x00\x01\x21\x01"
#clsd_position = b"\x6A\x04\x00\x02\x21\x01" #p


# Raw byte commands for MGMSG_MOT_GET_STATUSBITS
#id_ld = b"\x23\x02\x00\x00\x21\x01" #p20. Make the LED light flash
#op_mode = b"\x11\x05\x01\x00\x50\x01" #operation mode. Read 40 bytes afterwards

#%% setup some constants
cmd_tspc = 20 #minimum command time spacing in seconds
lst_cmd_time = dt.datetime.now() - dt.timedelta((cmd_tspc+10)/86400) #last command time
  

# %% make some defintions
def uot_sza_srise(lla=[43.66061, -79.398407, 167], horz='8.5'):
#  'lla = lat, lon, and altitude. horz = horizon angle'
  
  obs_loc = ephem.Observer()
  obs_loc.lat = np.str(lla[0])
  obs_loc.lon = np.str(lla[1])
  obs_loc.elevation = lla[2]
  obs_loc.horizon = horz #user definition of horizon. E.g. '8:30' for 8.5 degrees above
  s_pos = ephem.Sun(obs_loc)
  s_gen = ephem.Sun() #generic sun calc
  
#  utc_srise = obs_loc.next_rising(s_gen) #utc time for next sunrise
#  utc_sset = obs_loc.next_setting(s_gen) #utc time for next sunset
#  lcl_srise = ephem.localtime(utc_srise)
#  lcl_sset = ephem.localtime(utc_sset)
  
  curr_elv = s_pos.alt*180/np.pi #elevation angle
  
  if curr_elv>np.float64(horz): #next is sunset
    sec_sset = (obs_loc.next_setting(s_gen) - ephem.now())*86400 #seconds until next sunset
    return 1, sec_sset
  elif curr_elv<=np.float64(horz): #next is sunrise
    sec_srise = (obs_loc.next_rising(s_gen) - ephem.now())*86400 #seconds until next sunrise
    return 0, sec_srise


def dt2hr(dt_obj): #convert datetime object into hours into DAY
  
  dt_hms = dt_obj.strftime('%H%M%S') #string, hour minutes seconds
  dt_h = np.float64(dt_hms[0:2])+np.float64(dt_hms[2:4])/60+np.float64(dt_hms[5:])/3600
  
  return dt_h
  
  

def comp_srss(srss=[7.5, 17.75]): #computer sunrise sunset times (hours of day)
#  utc_offset = time.localtime().tm_gmtoff #offset to local time
#  comp_time = dt.datetime.now() #datetime object for current time
#  ct_hms=comp_time.strftime('%H%M%S') #computer time, hour minutes seconds
  
  ct_h = dt2hr(dt.datetime.now()) #= np.float64(ct_hms[0:2])+np.float64(ct_hms[2:4])/60+np.float64(ct_hms[5:])/3600 #current hour of day (with decimals)
  
  if srss[0]<srss[1]: #typical, when sunrise is before sunset
    if ct_h>srss[0] and ct_h<srss[1]: #next is sunset
      sec_sset = (srss[1]-ct_h)*3600 #seconds until next sunset
      return 1, sec_sset
    
    elif ct_h>srss[1]: #next is sunrise, end of day
      sec_srise = (24-ct_h+srss[0])*3600 #seconds until next sunrise
      return 0, sec_srise
    
    elif ct_h<srss[1]: #next is sunrise, beginning of day
      sec_srise = (srss[0]-ct_h)*3600 #seconds until next sunrise
      return 0, sec_srise
    
  elif srss[0]>srss[1]: #if sunset is "before" sun rise (e.g., using UTC time)
    if ct_h<srss[1]: #next is sunset, beginning of computer day
      sec_sset = (srss[1]-ct_h)*3600 #seconds until next sunset
      return 1, sec_sset
    
    elif ct_h>srss[1] and ct_h<srss[0]: #next is sunrise, middle of computer day
      sec_srise = (srss[0]-ct_h)*3600 #seconds until next sunrise
      return 0, sec_srise
    
    elif ct_h>srss[0]: #next is set, end of computer day
      sec_sset = (srss[1]+24-ct_h)*3600 #seconds until next sunset
      return 1, sec_sset
    


def open_or_closed(motor, vrb=True):
  #determine if motor is open or closed
  clsd_stat = b'*\x04\x06\x00\x81P\x01\x00\x02\x00\x00\x90' #closed byte status
  opn_stat  = b'*\x04\x06\x00\x81P\x01\x00\x01\x00\x00\x90' #open byte status
  st_bit = b"\x29\x04\x00\x00\x21\x01" #request status bits
  
  motor.write(st_bit); 
  mot_stat = motor.read(12) #NOTE: EXACTLY 12 bits need to be read. If too many, python will freeze waiting for more. If too few, you won't get them all this time (but will get some next time you read)
  if mot_stat == opn_stat: #shutter appears to be open
    if vrb: #verbose
      print('Shutter appears to be open')
    return 1 #1 for open
  elif mot_stat == clsd_stat: #shutter appears to be closed
    if vrb: #verbose
      print('Shutter appears to be closed')
    return 0 #0 for closed
  else:
    print('I am confused about the shutter position, going home')
    flip_move(fopn=False) #go to close position
    time.sleep(4) #time delay of 3 seconds to allow motor to park
    return 2 #2 for confused


def flip_move(fopn=True):
  # definining fopn=True as opening motor (90 degrees)
  opn_position = b"\x6A\x04\x00\x01\x21\x01"
  clsd_position = b"\x6A\x04\x00\x02\x21\x01" #p
  
  if fopn: #open the shutter
    motor.write(opn_position)
    print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + ' opened')
  else: #close the shutter
    motor.write(clsd_position)
    print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + ' closed')
  
  time.sleep(3) #add in short delay to allow motor to fully flip


def lp_subhk(m_opn=False): #loop sub-check
  lp_oc = open_or_closed(motor, vrb=False) #check motor position, silently
  if lp_oc==1 and not m_opn: #shutter is open when it should be closed
    print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + ' WARNING: shutter left open at night!! Attempting to close.' )
    flip_move(fopn=False)
    
  elif lp_oc==0 and m_opn: #shutter is closed when it should be open
    print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + ' whoops, shutter was closed during daytime. Attempting to open.')
    flip_move(fopn=True)
    
  

def lp_check(op_time, cmd_tspc, m_opn=False, swp_end=False):
  # as an alternative to a long sleep, this script loops through every so often
  # to check the shutter position
  
  lp_subhk(m_opn) #loop sub-check (first time through)
  while op_time>(dt.datetime.now()+dt.timedelta((cmd_tspc)/86400)): #keep checking until it's close to the next operation time
    lp_subhk(m_opn) #loop sub-check
    time.sleep(cmd_tspc) #take a little nap
  
  sec_until = (op_time - dt.datetime.now()).total_seconds() #seconds until next command
  time.sleep(sec_until) #take a final nap
  
  if swp_end: #swap position at end
    flip_move(fopn=not m_opn) #open or close (opposite of what it should have been before)
  
  return open_or_closed(motor, vrb=False) #check motor position, silently
  
  
  


# %% initialize as motor
srl_num = b"37872128" #serial number for particular device (written on the side). Could also try thorlabs_apt

# Recommended d2xx setup instructions from Thorlabs.
motor = ftd2xx.openEx(srl_num)
#print(motor.getDeviceInfo())
motor.setBaudRate(115200)
motor.setDataCharacteristics(constants.BITS_8, constants.STOP_BITS_1, constants.PARITY_NONE)
time.sleep(.05)
motor.purge()
time.sleep(.05)
motor.resetDevice()
motor.setFlowControl(constants.FLOW_RTS_CTS, 0, 0)
motor.setRts()


#motor.close()
#motor.write(up_position)
#motor.write(down_position)
#motor.write(op_mode); motor.read(40)
#motor.write(st_bit); motor.read(12)
#raise ValueError('p')

# %% main loop
try:
  while True: #infinite loop
    sc_lst = (dt.datetime.now()-lst_cmd_time).total_seconds() #seconds since the last command
    if sc_lst < cmd_tspc: #setting minimum delay between loops to help prevent flipping back and forth...
      time.sleep(sc_lst)
      
    else:
      oorc = open_or_closed(motor) #check motor position
      lst_cmd_time = dt.datetime.now() #get current time
      
      if oorc<2: #if it's open OR closed
#        dorn, sec2go = uot_sza_srise(lla=[43.66061, -79.398407, 167], horz='15.5') #specify when to next open/close shutter
        dorn, sec2go = comp_srss(srss=[7.5, 17.75]) #computer times to open/close shutter
        
        sec2go = sec2go+20 #adds in a few seconds delay to reduce chance of motor flipping back and forth at ends of day
        nxt_time = dt.datetime.now() + dt.timedelta((sec2go)/86400) #next time a command is to take place
        
        if dorn==1:
          print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + '. It appears to be daytime.')
        elif dorn==0:
          print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + '. It appears to be nighttime.')
        
        
        oorc = lp_check(dt.datetime.now()+dt.timedelta(5/86400), cmd_tspc, m_opn=bool(dorn), swp_end=False) #open or close the shutter if it's in the wrong position

          
        if dorn==1 and oorc==1: #daytime, shutter open
          print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + '. Shutter to close' + ' at ' + nxt_time.strftime('%H:%M:%S %Y/%m/%d')  )
          lp_check(nxt_time, cmd_tspc, m_opn=bool(dorn), swp_end=True)
#          print('Night. Closed')
          
        elif dorn==0 and oorc==0: #nighttime, shutter closed
          print(dt.datetime.now().strftime('%H:%M:%S %Y/%m/%d') + '. Shutter to open' + ' at ' + nxt_time.strftime('%H:%M:%S %Y/%m/%d')  )
          lp_check(nxt_time, cmd_tspc, m_opn=bool(dorn), swp_end=True)
#          print('Morning time. Opened')
        
        time.sleep(3) #add short delay in each loop
      
      
    
except KeyboardInterrupt:
  print('Interrupted sza_shutter due to keyboard input!')
  motor.close()



  










