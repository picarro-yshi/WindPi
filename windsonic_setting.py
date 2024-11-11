# quick code to change gill instrument settings, get readings.

option = 2  # 1: change setting, 2: continuous run
cmd = "P3"  # P3 is the command for data output rate = 4 Hz, replace with yours
COMMAND = ("%s\r\n" % cmd).encode()
BAUDRATE = 19200

import time
import serial

import platform
opsystem = platform.system()  # 'Linux', 'Windows', 'Darwin'
print(opsystem)

import serial.tools.list_ports as ls
print([p.device for p in ls.comports()])


with open("par1/port.txt", "r") as f:
    PORT = f.read()  # '/dev/ttyUSB0'

def change_settings():
    gill = serial.Serial(PORT, BAUDRATE)
    gill.write(b"*\r")  # enter configuration mode
    gill.write(COMMAND)
    # gill.write(b"P3\r\n")
    reading = gill.readline().decode()
    print(reading)
    print(len(reading))
    gill.close()
    return reading


def run():
    wind = serial.Serial(PORT, BAUDRATE)
    print(wind.name)
    
    while True:
        print(time.time())
        # using ser.readline() assumes each line contains a single reading
        reading = wind.readline().decode()
        print(reading)

    
def run_ltd(n):  # get n values
    wind = serial.Serial(PORT, BAUDRATE)
    for i in range(n):
        x = wind.readline().decode()
        # print(x)
        y = x.split(',')
        print(float(y[1]), float(y[2]))


if __name__ == "__main__":
    
    if option == 1:
        reading = change_settings()
        if reading[0] == "*" and len(reading) == 4:
            print("command sent successfully!! Power off then on to see the effect.")
        else:
            print("command NOT sent, try again.")
    elif option == 2:
        run()  # continous output data
    elif option == 3:
        run_ltd(10)  # get n data


# @author: Yilin Shi | 2024.7.26
