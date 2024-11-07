# Wind anemometer model "GMX500" data recorder control code.
# run in terminal, ssh. last updated: 2024.10.31

import time
import os
import shutil
import sys
import tty
import termios
import select

import serial
import serial.tools.list_ports as ls
print([p.device for p in ls.comports()])

# for I2C board
import board
from adafruit_ina219 import INA219

# custom parameters
PORT = '/dev/ttyUSB0'
BAUDRATE = 19200
VOLTAGE_MIN = 12.2  # battery is 12 V, lower than this means battery is dead.

# csv header: 18 items
HEADER = "epoch_time," \
         "local_clock_time," \
         "velocity_u_m/s," \
         "velocity_v_m/s," \
         "Direction," \
         "Speed_m/s," \
         "Corrected_Direction," \
         "Corrected_Speed_m/s," \
         "Pressure_hPa," \
         "Relative_Humidity_%," \
         "Temperature_C," \
         "Dew_point_C," \
         "GPS_Latitude," \
         "GPS_longitude," \
         "GPS_Height_m," \
         "GPS_Time," \
         "Supply_Voltage," \
         "Battery_V\n"
LOCAL_DATA_PATH = "/home/picarro/Wind_data"  # folder to save data locally
RDRIVE_FOLDER = "/mnt/r/crd_G9000/AVXxx/Roof_Tower_Data/Anemometer/GMX500"
WARNING_MSG = os.path.join(RDRIVE_FOLDER, "battery_warning.txt")
if os.path.isfile(WARNING_MSG):
    os.remove(WARNING_MSG)


# get keyboard input
class NonBlockingConsole(object):
    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_data(self):
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            return sys.stdin.read(1)
        return False

nbc = NonBlockingConsole()


def record(x, v, local_file_path):
    y = x.split(',')

    epoch = time.time()
    clock_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # occasionally I2C board sents out empty strings, this serves as a validation.
    a1 = float(y[1])  # u-velocity
    a2 = float(y[2])  # v-velocity
    a3 = int(y[3])  # Direction
    a4 = float(y[4])  # Speed
    wind_dir = int(y[5])  # Corrected_Direction
    wind_speed = float(y[6])  # Corrected_Speed
    a5 = float(y[7])  # Pressure
    a6 = float(y[8])  # Humidity
    a7 = float(y[9])  # Temperature
    a8 = float(y[10])  # Dew point
    a9, a10, a11 = y[11].split(':')  # GPS_Latitude, GPS_longitude, GPS_Height
    a13 = float(y[13])  # supply voltage

    with open(local_file_path, "a") as f:
        # need a space before clock time so excel reads it as string
        f.write("%s, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" %
                (epoch, clock_time, a1, a2, a3, 
                 a4, wind_dir, wind_speed, a5, a6, 
                 a7, a8, a9, a10, a11, 
                 y[12], a13, v))


def run_wind():
    filename = time.strftime("%Y%m%d_%H")
    # create folder of the day on local drive
    local_folder_day = os.path.join(LOCAL_DATA_PATH, filename[:8])
    if not os.path.isdir(local_folder_day):
        os.mkdir(local_folder_day)

    local_file_path = os.path.join(local_folder_day, filename + ".csv")
    with open(local_file_path, "w") as f:
        f.write(HEADER)

    # create folder of the day on r-drive
    r_folder_day = os.path.join(RDRIVE_FOLDER, filename[:8])
    if not os.path.isdir(r_folder_day):
        os.mkdir(r_folder_day)

    uncopied = []  # uncopied csv files, for try again later

    while 1:
        kb = nbc.get_data()  # keyboard input
        if kb:
            if kb == "q":
                print("-> quit...")
                # copy last file to R drive
                file_path = os.path.join(LOCAL_DATA_PATH, filename[:8], filename + ".csv")
                r_folder_path = os.path.join(RDRIVE_FOLDER, filename[:8])
                try:
                    shutil.copy2(file_path, r_folder_path)  # source, destination
                except:
                    print("! copy last file to r-drive failed, please copy manually: %s.csv" % filename)
                sys.exit()


        now = time.strftime("%Y%m%d_%H")  # 20241010_14

        # create a new csv every hour and copy to r-drive
        if now[-2:] != filename[-2:]:
            # copy previous hour csv to r-drive
            try:
                shutil.copy2(local_file_path, r_folder_day)  # source, destination
            except:
                uncopied.append([local_file_path, r_folder_day])
                print("! copy to r-drive failed: %s.csv, will try again later." % filename)

            # data failed to copy previously: try again
            if uncopied:
                for i in range(len(uncopied)):
                    try:
                        shutil.copy2(uncopied[0][0], uncopied[0][1])
                        print("* copy to r-drive successful: %s.csv" % uncopied[0][0])
                        uncopied.pop(0)
                    except:
                        pass

            # create a new folder every day
            if (now[-2:] == "00") and (filename[-2:] == "23"):
                # locally
                local_folder_day = os.path.join(LOCAL_DATA_PATH, now[:8])
                os.mkdir(local_folder_day)

                # on r-drive
                r_folder_day = os.path.join(RDRIVE_FOLDER, now[:8])
                os.mkdir(r_folder_day)

            filename = now
            local_file_path = os.path.join(local_folder_day, filename + ".csv")
            with open(local_file_path, "w") as f:
                f.write(HEADER)

        # get battery voltage from I2C board
        bus_voltage = ina219.bus_voltage  # voltage on V- (load side)
        shunt_voltage = ina219.shunt_voltage  # voltage between V+ and V- across the shunt
        v = round(bus_voltage + shunt_voltage, 5)
        print("Battery: %s V" % v)
        if v < VOLTAGE_MIN:
            x = "! Warning, battery is dead: %s" % time.ctime()
            try:
                with open(WARNING_MSG, 'a') as f:
                    f.write(x + "\n")
            except:
                pass
            print(x)

        x = wind.readline().decode()
        print(x)
        try:
            record(x, v, local_file_path)
        except:
            print("- invalid data.")


if __name__ == "__main__":
    wind = serial.Serial(PORT, BAUDRATE)
    i2c_bus = board.I2C()  # uses board.SCL and board.SDA
    ina219 = INA219(i2c_bus)
    
    tag = 1
    # check I2C board communication
    try:
        bus_voltage = ina219.bus_voltage  # voltage on V- (load side)
        shunt_voltage = ina219.shunt_voltage  # voltage between V+ and V- across the shunt

        # INA219 measure bus voltage on the load side. So PSU voltage = bus_voltage + shunt_voltage
        print("Voltage (VIN+) : {:6.3f}   V".format(bus_voltage + shunt_voltage))
        print("Voltage (VIN-) : {:6.3f}   V".format(bus_voltage))
        print("Shunt Voltage  : {:8.5f} V".format(shunt_voltage))
        print("Communication with I2C board established.")
    except:
        print("Cannot read from I2C board.")
        tag = 0
        
    # check anemometer communication
    try:
        x = wind.readline().decode()
        print(x)
        print("Communication with anemometer established.")
    except:
        print("Cannot read from anemometer.")
        tag = 0
    
    if tag:
        run_wind()


# @author: Yilin Shi | 2024.10.31
# shiyilin890@gmail.com
# Bog the Fat Crocodile vvvvvvv
#                       ^^^^^^^
