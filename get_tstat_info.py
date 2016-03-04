#!/usr/bin/python

# Honeywell info
USERNAME="email"
PASSWORD="password"
DEVICE_ID=deviceid

# Graphite Server
#CARBON_SERVER = 'graphiteserver'
CARBON_SERVER = 'localhost'
CARBON_PORT = 2003

############################ End settings ############################

import urllib
import json
import datetime
import re
import time
import time
import httplib
import sys
import os
import stat
import socket

AUTH="https://mytotalconnectcomfort.com/portal"

cookiere=re.compile('\s*([^=]+)\s*=\s*([^;]*)\s*')

def client_cookies(cookiestr,container):
  if not container: container={}
  toks=re.split(';|,',cookiestr)
  for t in toks:
    k=None
    v=None
    m=cookiere.search(t)
    if m:
      k=m.group(1)
      v=m.group(2)
      if (k in ['path','Path','HttpOnly']):
        k=None
        v=None
    if k: 
      #print k,v
      container[k]=v
  return container

def export_cookiejar(jar):
  s=""
  for x in jar:
    s+='%s=%s;' % (x,jar[x])
  return s

def send_msg(message):
    print 'sending message:\n%s' % message
    sock = socket.socket()
    sock.connect((CARBON_SERVER, CARBON_PORT))
    sock.sendall(message)
    sock.close()

def get_login():
    
    cookiejar=None
    headers={"Content-Type":"application/x-www-form-urlencoded",
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding":"sdch",
            "Host":"mytotalconnectcomfort.com",
            "DNT":"1",
            "Origin":"https://mytotalconnectcomfort.com/portal",
            "User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36"
        }
    conn = httplib.HTTPSConnection("mytotalconnectcomfort.com")
    conn.request("GET", "/portal/",None,headers)
    r0 = conn.getresponse()
    
    for x in r0.getheaders():
      (n,v) = x
      if (n.lower() == "set-cookie"): 
        cookiejar=client_cookies(v,cookiejar)
    location = r0.getheader("Location")

    retries=5
    params=urllib.urlencode({"timeOffset":"240",
        "UserName":USERNAME,
        "Password":PASSWORD,
        "RememberMe":"true"})
    newcookie=export_cookiejar(cookiejar)

    headers={"Content-Type":"application/x-www-form-urlencoded",
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding":"sdch",
            "Host":"mytotalconnectcomfort.com",
            "DNT":"1",
            "Origin":"https://mytotalconnectcomfort.com/portal/",
            "Cookie":newcookie,
            "User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36"
        }
    conn = httplib.HTTPSConnection("mytotalconnectcomfort.com")
    conn.request("POST", "/portal/",params,headers)
    r1 = conn.getresponse()
    
    for x in r1.getheaders():
      (n,v) = x
      if (n.lower() == "set-cookie"): 
        cookiejar=client_cookies(v,cookiejar)
    cookie=export_cookiejar(cookiejar)
    location = r1.getheader("Location")

    if ((location == None) or (r1.status != 302)):
        print("ErrorNever got redirect on initial login  status={0} {1}".format(r1.status,r1.reason))
        return

    code=str(DEVICE_ID)

    t = datetime.datetime.now()
    utc_seconds = (time.mktime(t.timetuple()))
    utc_seconds = int(utc_seconds*1000)

    location="/portal/Device/CheckDataSession/"+code+"?_="+str(utc_seconds)
    headers={
            "Accept":"*/*",
            "DNT":"1",
            "Accept-Encoding":"plain",
            "Cache-Control":"max-age=0",
            "Accept-Language":"en-US,en,q=0.8",
            "Connection":"keep-alive",
            "Host":"mytotalconnectcomfort.com",
            "Referer":"https://mytotalconnectcomfort.com/portal/",
            "X-Requested-With":"XMLHttpRequest",
            "User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36",
            "Cookie":cookie
        }
    # 60 minutes on the same cookie hehe (prevents honeywell from banning the user from to many login attempts)
    for x in range(0, 60):
        get_status(location,headers)

def get_status(location, headers):
    timestamp = int(time.time())
    conn = httplib.HTTPSConnection("mytotalconnectcomfort.com")
    conn.request("GET", location,None,headers)
    r3 = conn.getresponse()
    if (r3.status != 200):
      print("Error Didn't get 200 status on R3 status={0} {1}".format(r3.status,r3.reason))
      return

    rawdata=r3.read()
    j = json.loads(rawdata)

    temp       = j['latestData']['uiData']["DispTemperature"]
    humid      = j['latestData']['uiData']["IndoorHumidity"]
    cool_set   = j['latestData']['uiData']["CoolSetpoint"]
    heat_set   = j['latestData']['uiData']["HeatSetpoint"]
    sys_status = j['latestData']['uiData']["EquipmentOutputStatus"]
    fan_status = j['latestData']['fanData']["fanIsRunning"]

    lines = [
        "home.Indoor_Temperature {0} {1}".format(temp, timestamp),
        "home.Indoor_Humidity {0} {1}".format(humid, timestamp),
        "home.Cool_SetPoint {0} {1}".format(cool_set, timestamp),
        "home.Heat_SetPoint {0} {1}".format(heat_set, timestamp),
    ]

    if (sys_status == 1):
        # heat
        lines.append("home.heat_status 1 {0}".format(timestamp))
    elif (sys_status == 2):
        # cooling
        lines.append("home.cool_status 1 {0}".format(timestamp))
    if fan_status and sys_status == 0:
        lines.append("home.fan_status 1 {0}".format(timestamp))

    message = '\n'.join(lines) + '\n'
    send_msg(message)
    time.sleep(60)

get_login()
