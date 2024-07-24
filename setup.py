COMMAND = "P3"  # data rate 4 Hz

PORT = '/dev/ttyUSB2'
BAUDRATE = 19200

import time
import serial

import platform
opsystem = platform.system()  # 'Linux', 'Windows', 'Darwin'
print(opsystem)

import serial.tools.list_ports as ls
print([p.device for p in ls.comports()])


def change_settings():
    # cmd = "%s\n\r" % COMMAND
    gill = serial.Serial(PORT, BAUDRATE)
    gill.write(b"*\r")  # enter configuration mode
    # gill.write(b"P3\n\r")
    gill.write(b"%s\n\r" % COMMAND)
    print(gill.readline().decode())

    
def run_ltd(n):  # get n values
    wind = serial.Serial(PORT, BAUDRATE)
    for i in range(n):
        x = wind.readline().decode()
        # print(x)
        y = x.split(',')
        print(float(y[1]), float(y[2]))


def run():
    wind = serial.Serial(PORT, BAUDRATE)
    print(wind.name)
    
    while True:
        print(time.time())
        # using ser.readline() assumes each line contains a single reading
        reading = wind.readline().decode()
        print(reading)


if __name__ == "__main__":
    # run_ltd(10)  # get n data
    # run()  # continous output data
    change_settings()

