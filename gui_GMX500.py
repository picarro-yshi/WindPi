# wind anemometer model "GMX500" data recorder control code, 2024.10.9

### custom parameters  ###
# anemometer
BAUDRATE = 19200

# I2C board
VOLTAGE_MIN = 0.884  # battery is 12 V, lower than this means battery is dead.

# GUI
LOCAL_DATA_PATH = "/home/picarro/Wind_data"  # folder to save data locally
GUI_REFRESH_TIME = 1  # s
PLOT_WINDOW_WIND = 10  # min, time length for wind data plot
PLOT_WINDOW_V = 6  # hour, time length for battery data plot
INTERVAL_V = 5  # min, plot a battery voltage point every # mins
MONTH = 3  # delete files that is how many months old

# csv header: 15 items
HEADER = "epoch_time," \
         "local_clock_time," \
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

import sys
import platform
import os
import shutil
import time
import numpy as np
import csv

import serial
import serial.tools.list_ports as ls
print([p.device for p in ls.comports()])

opsystem = platform.system()  # 'Linux', 'Windows', 'Darwin'
print(opsystem)
print("hostname: ", platform.node())

import warnings
warnings.filterwarnings('ignore')


## Qt GUI
if 'rasp' in platform.node():
    RASPI = 1
else:
    RASPI = 0

if RASPI:  # on a raspberry pi, use PySide6
    from PySide6.QtGui import QPixmap, QIcon, QAction
    from PySide6.QtCore import Qt, QTimer, QSize
    from PySide6.QtWidgets import (
        QApplication,
        QTabWidget,
        QPushButton,
        QMessageBox,
        QTextEdit,
        QLineEdit,
        QToolButton,
        QCheckBox,
        QGridLayout,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QGroupBox,
        QProgressBar,
        QComboBox,
        QToolBar,
        QMainWindow,
        QFileDialog,
    )
    from PySide6.QtCore import QObject, QThread, Signal

    # for I2C board
    import board
    from adafruit_ina219 import INA219

else:
    # use PyQt6
    from PyQt6.QtGui import QPixmap, QIcon, QAction, QFont
    from PyQt6.QtCore import Qt, QTimer, QSize
    from PyQt6.QtWidgets import (
        QApplication,
        QTabWidget,
        QPushButton,
        QMessageBox,
        QTextEdit,
        QLineEdit,
        QToolButton,
        QCheckBox,
        QGridLayout,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QGroupBox,
        QProgressBar,
        QComboBox,
        QToolBar,
        QMainWindow,
        QFileDialog,
    )
    from PyQt6.QtCore import QObject, QThread
    from PyQt6.QtCore import pyqtSignal as Signal

from matplotlib import pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from windrose import WindroseAxes

# customized files
import style

global stoprun  # 1 stop thread, 0 keep running
global clearplot  # 1 clear plots, 0 not


TEMP_FILE_WIND = os.path.join(LOCAL_DATA_PATH, "tempwind.csv")
TEMP_FILE_V = os.path.join(LOCAL_DATA_PATH, "tempv.csv")

# Step 1: Create a worker class
class Worker(QObject):
    finished = Signal()
    progress = Signal(str)

    def run(self):
        """Long-running task."""
        global stoprun
        stoprun = 0
        global clearplot
        clearplot = 0

        total_wind_pts = PLOT_WINDOW_WIND * 60
        total_v_pts = int(60 / INTERVAL_V * PLOT_WINDOW_V)

        with open("par1/port.txt", "r") as f:
            PORT = f.read()  # '/dev/ttyUSB2'

        with open("par1/rdrive.txt", "r") as f:
            RDRIVE_FOLDER = f.read()

        wind = serial.Serial(PORT, BAUDRATE)
        print('anemometer USB port: ', wind.name)

        i2c_bus = board.I2C()  # uses board.SCL and board.SDA
        ina219 = INA219(i2c_bus)

        filename = time.strftime("%Y%m%d_%H")
        self.progress.emit(filename)

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
            
        uncopied = []  # uncopied csv files, try again later
        plot_data_wind = []
        
        # initiate the voltage part
        time_tag = time.time()
        plot_data_v = []
        for i in range(2):
            bus_voltage = ina219.bus_voltage
            shunt_voltage = ina219.shunt_voltage
            v = round(bus_voltage + shunt_voltage, 2)
            plot_data_v.append([time_tag, v])
            
        with open(TEMP_FILE_V, 'w', newline='') as f:
            write = csv.writer(f)
            write.writerows(plot_data_v)
        

        while True:
            if stoprun:
                break
                
            if clearplot:
                plot_data_wind = []
                plot_data_v = []
                clearplot = 0
                print('plot cleared.')

            epoch = time.time()
            clock_time = time.strftime('%Y-%m-%d %H:%M:%S')

            now = time.strftime("%Y%m%d_%H")  # 20240712_14
            
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
                self.progress.emit(filename)

            # get battery voltage from I2C board
            bus_voltage = ina219.bus_voltage  # voltage on V- (load side)
            shunt_voltage = ina219.shunt_voltage  # voltage between V+ and V- across the shunt
            v = round(bus_voltage + shunt_voltage, 5)
            # print("Battery: %s V" % v)

            # data for battery voltage plot
            if epoch - time_tag > INTERVAL_V * 60:
                plot_data_v.append([epoch, round(v, 2)])

                if len(plot_data_v) > total_v_pts:
                    plot_data_v.pop(0)

                with open(TEMP_FILE_V, 'w', newline='') as f:
                    write = csv.writer(f)
                    write.writerows(plot_data_v)

                time_tag = epoch

            try:
                x = wind.readline().decode()
                # print(x)
                y = x.split(',')
                # occasionally I2C board sents out empty strings, this serves as a validation.
                a1 = int(y[1])  # Direction
                a2 = float(y[2])  # Speed
                wind_dir = int(y[3])  # Corrected_Direction
                wind_speed = float(y[4])  # Corrected_Speed
                a3 = float(y[5])  # Pressure
                a4 = float(y[6])  # Humidity
                a5 = float(y[7])  # Temperature
                a6 = float(y[8])  # Dew point
                a7, a8, a9 = y[9].split(':')  # GPS_Latitude, GPS_longitude, GPS_Height
                a11 = float(y[11])  # supply voltage

                with open(local_file_path, "a") as f:
                    # need a space before clock time so excel reads it as string
                    f.write("%s, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" %
                            (epoch, clock_time, a1, a2, wind_dir, wind_speed,
                             a3, a4, a5, a6, a7, a8, a9, y[10], a11, v))

                # data for wind rose plot
                plot_data_wind.append([wind_dir, wind_speed])
                if len(plot_data_wind) > total_wind_pts:
                    plot_data_wind.pop(0)

                with open(TEMP_FILE_WIND, 'w', newline='') as f:
                    write = csv.writer(f)
                    write.writerows(plot_data_wind)

            except:
                pass
                # print("- invalid data.")

        self.finished.emit()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(200, 200, 1200, 800)
        self.setWindowTitle("Wind")
        self.set_window_layout()

    def add_img(self, imgpath, label, x, y):  # image path, label, x scale, y scale
        p1 = QPixmap(imgpath)
        p2 = p1.scaled(
            x,
            y,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        label.setPixmap(p2)

    def set_window_layout(self):
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)

        topLayout = QHBoxLayout()
        bottomLayout = QHBoxLayout()
        mainLayout.addLayout(topLayout, 5)
        mainLayout.addLayout(bottomLayout, 95)

        self.tabs = QTabWidget()
        bottomLayout.addWidget(self.tabs)

        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tabs.addTab(self.tab1, " ⬥ Data Display ")
        self.tabs.addTab(self.tab2, " ⬥ Settings ")

        # title layout
        logoLabel = QLabel()
        self.add_img("icons/picarro.png", logoLabel, 250, 100)
        # logoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titleLabel = QLabel('Real Time Wind Data Recorder for "GMX500" ')
        titleLabel.setStyleSheet(style.headline1())
        titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        topLayout.addWidget(logoLabel)
        topLayout.addStretch(1)
        topLayout.addWidget(titleLabel)
        topLayout.addStretch(2)

        # tab1 layout
        tab1Layout = QHBoxLayout()
        self.tab1.setLayout(tab1Layout)

        leftLayout = QVBoxLayout()
        rightLayout = QVBoxLayout()
        gap = QLabel("")
        tab1Layout.addLayout(leftLayout)
        tab1Layout.addWidget(gap)
        tab1Layout.addLayout(rightLayout)

        # tab1 left part
        figure1Layout = QVBoxLayout()
        figure1Layout.setContentsMargins(15, 30, 15, 10)
        box1 = QGroupBox(" Battery Voltage Time Series Plot (%s h)" % PLOT_WINDOW_V)
        box1.setStyleSheet(style.box1())
        box1.setLayout(figure1Layout)

        self.Layout = QVBoxLayout()
        leftLayout.addWidget(box1)
        leftLayout.addLayout(self.Layout)

        # tab1 right part
        figure2Layout = QVBoxLayout()
        figure2Layout.setContentsMargins(15, 30, 15, 10)
        box2 = QGroupBox(" Wind Rose Plot (%s min)" % PLOT_WINDOW_WIND)
        box2.setStyleSheet(style.box2())
        box2.setLayout(figure2Layout)
        rightLayout.addWidget(box2)

        # time series plot
        self.figure1 = plt.figure()
        #self.figure1.tight_layout()
        self.canvas1 = FigureCanvas(self.figure1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        self.toolbar1.setFixedHeight(30)
        self.batteryLabel = QLabel()
        self.batteryLabel.setStyleSheet(style.red2())

        layout1 = QHBoxLayout()
        figure1Layout.addWidget(self.canvas1)
        figure1Layout.addLayout(layout1)
        layout1.addWidget(self.toolbar1)
        layout1.addWidget(self.batteryLabel)

        # windrose plot
        self.figure2 = plt.figure()
        self.canvas2 = FigureCanvas(self.figure2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        self.toolbar2.setFixedHeight(30)

        figure2Layout.addWidget(self.canvas2)
        figure2Layout.addWidget(self.toolbar2)

        self.createLayout1()

        # tab2 layout
        self.tab2Layout = QHBoxLayout()
        self.tab2.setLayout(self.tab2Layout)
        self.createLayout2()
        print('GUI layout created.')

        if RASPI:  # on a raspberry pi
            self.delete_folders()

        # timer
        self.timer_plot = QTimer()
        self.timer_plot.setInterval(GUI_REFRESH_TIME * 1000)
        self.timer_plot.timeout.connect(self.plot_wind)

        self.timer_battery = QTimer()
        self.timer_battery.setInterval(INTERVAL_V * 60 * 1000)
        self.timer_battery.timeout.connect(self.plot_voltage)


    def createLayout1(self):  # tab1
        layout1 = QHBoxLayout()
        layout2 = QHBoxLayout()
        bottomLayout = QHBoxLayout()
        self.Layout.addLayout(layout1)
        self.Layout.addLayout(layout2)
        self.Layout.addLayout(bottomLayout)

        # line 1
        label11 = QLabel("Wind Speed (m/s):")
        label11.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.windSpeedLabel = QLabel()
        self.windSpeedLabel.setStyleSheet(style.blue1())
        self.windSpeedLabel.setFixedHeight(24)
        self.windSpeedLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label12 = QLabel("Wind Direction (°):")
        label12.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.windDirLabel = QLabel()
        self.windDirLabel.setStyleSheet(style.blue1())
        self.windDirLabel.setFixedHeight(24)
        self.windDirLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label13 = QLabel("Battery Voltage (V):")
        label13.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.voltageLabel = QLabel()
        self.voltageLabel.setStyleSheet(style.green1())
        self.voltageLabel.setFixedHeight(24)
        self.voltageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout1.addWidget(label11)
        layout1.addWidget(self.windSpeedLabel)
        layout1.addWidget(label12)
        layout1.addWidget(self.windDirLabel)
        layout1.addWidget(label13)
        layout1.addWidget(self.voltageLabel)

        # line 2
        label21 = QLabel("Folder:")
        self.folderLineEdit = QLineEdit("")
        self.folderLineEdit.setToolTip("Path of R drive folder to store data:")
        try:
            with open("par1/rdrive.txt", "r") as f:
                temp = f.read()
            self.folderLineEdit.setText(temp)
        except:
            print("No folder path loaded.")
        
        folderButton = QPushButton("Browse")
        folderButton.clicked.connect(self.brouse_folder)

        layout2.addWidget(label21)
        layout2.addWidget(self.folderLineEdit)
        layout2.addWidget(folderButton)

        # line 3
        layout3 = QVBoxLayout()
        startButtonLayout = QVBoxLayout()
        clearButtonLayout = QVBoxLayout()
        stopButtonLayout = QVBoxLayout()

        bottomLayout.addLayout(layout3, 68)
        bottomLayout.addLayout(startButtonLayout, 10)
        bottomLayout.addLayout(clearButtonLayout, 12)
        bottomLayout.addLayout(stopButtonLayout, 10)

        portLayout = QHBoxLayout()
        self.hintLabel = QLabel()
        self.hintLabel.setStyleSheet(style.grey1())
        self.hintLabel.setFixedHeight(30)

        layout3.addLayout(portLayout)
        layout3.addWidget(self.hintLabel)
        layout3.addStretch()

        portLabel = QLabel("Port:")
        portLabel.setToolTip("Serial-USB port name of Anemometer")
        self.portComboBox = QComboBox()
        self.portComboBox.setFixedWidth(130)
        self.port_get()  # fill dropdown menu
        try:
            with open("par1/port.txt", "r") as f:
                temp = f.read()
            self.portComboBox.setCurrentText(temp)
        except:
            print("load port failed.")

        portgetButton = QPushButton("Get")
        portgetButton.clicked.connect(self.port_get)
        portgetButton.setToolTip("Get all available USB ports on this computer.")
        portDetectButton = QPushButton("Detect")
        portDetectButton.clicked.connect(self.port_detect)
        portDetectButton.setToolTip("Detect if anemometer is connected to this port.")
        self.portHintLabel = QLabel("  ")

        portLayout.addWidget(portLabel)
        portLayout.addWidget(self.portComboBox)
        portLayout.addWidget(portgetButton)
        portLayout.addWidget(portDetectButton)
        portLayout.addWidget(self.portHintLabel)

        # round buttons
        self.StartButton = QToolButton()
        self.StartButton.setIcon(QIcon("icons/start1.png"))
        self.StartButton.setIconSize(QSize(40, 40))
        self.StartButton.clicked.connect(self.start)
        startLabel = QLabel(" Start")
        startLabel.setAlignment(Qt.AlignmentFlag.AlignTop)

        startButtonLayout.addWidget(self.StartButton)
        startButtonLayout.addWidget(startLabel)

        self.StopButton = QToolButton()
        self.StopButton.setIcon(QIcon("icons/stop1.png"))
        self.StopButton.setIconSize(QSize(40, 40))
        self.StopButton.clicked.connect(self.stop)
        self.StopButton.setEnabled(False)
        stopLabel = QLabel("  Stop")
        stopLabel.setAlignment(Qt.AlignmentFlag.AlignTop)

        stopButtonLayout.addWidget(self.StopButton)
        stopButtonLayout.addWidget(stopLabel)
        
        self.ClearButton = QToolButton()
        self.ClearButton.setIcon(QIcon("icons/clear.png"))
        self.ClearButton.setIconSize(QSize(40, 40))
        self.ClearButton.clicked.connect(self.clear_plots)
        self.ClearButton.setEnabled(False)
        self.ClearButton.setToolTip("Clear plots")
        clearLabel = QLabel("Clear Plots")
        clearLabel.setAlignment(Qt.AlignmentFlag.AlignTop)

        clearButtonLayout.addWidget(self.ClearButton)
        clearButtonLayout.addWidget(clearLabel)        


    def createLayout2(self):
        leftlayout = QVBoxLayout()
        rightlayout = QVBoxLayout()
        gap = QLabel()
        self.tab2Layout.addLayout(leftlayout, 48)
        self.tab2Layout.addWidget(gap, 2)
        self.tab2Layout.addLayout(rightlayout, 50)

        # left part
        layout1 = QVBoxLayout()
        layout1.setContentsMargins(20, 40, 20, 10)
        layout2 = QVBoxLayout()
        layout2.setContentsMargins(20, 40, 20, 10)
        layout3 = QVBoxLayout()

        box1 = QGroupBox("Anemometer Default Settings:")
        box1.setStyleSheet(style.box5())
        box1.setLayout(layout1)

        box2 = QGroupBox("GUI Default Settings:")
        box2.setStyleSheet(style.box5())
        box2.setLayout(layout2)

        leftlayout.addWidget(box1)
        leftlayout.addWidget(box2)
        leftlayout.addLayout(layout3)
        leftlayout.addStretch()

        # anemometer settings
        grid1 = QGridLayout()
        gap = QLabel()
        x = "- These parameters cannot be changed. \n" \
            "- To view more settings of the anemometer: \n" \
            "  install 'MetSet' software on a Windows computer, " \
            "(if computer cannot recognize the anemometer, " \
            "install 'Driver for UPort 1200'), then view the settings in MetSet." \

        howlabel1 = QLabel(x)
        howlabel1.setWordWrap(True)

        layout1.addLayout(grid1)
        layout1.addWidget(gap)
        layout1.addWidget(howlabel1)

        label11a = QLabel("• Data Output Rate: ")
        label11b = QLabel("1 Hz")
        label12a = QLabel("• Baudrate: ")
        label12b = QLabel("19200")
        label13a = QLabel("• Unit of Wind Speed: ")
        label13b = QLabel("m/s")
        label14a = QLabel("• Unit of Direction: ")
        label14b = QLabel("degree")
        label15a = QLabel("• Unit of Temperature: ")
        label15b = QLabel("°C")
        label16a = QLabel("• Unit of Pressure: ")
        label16b = QLabel("hPa")
        label17a = QLabel("• Unit of Relative Humidity: ")
        label17b = QLabel("%")
        label18a = QLabel("• Unit of GPS Height: ")
        label18b = QLabel("m")

        grid1.addWidget(label11a, 0, 0)
        grid1.addWidget(label11b, 0, 1)
        grid1.addWidget(label12a, 1, 0)
        grid1.addWidget(label12b, 1, 1)
        grid1.addWidget(label13a, 2, 0)
        grid1.addWidget(label13b, 2, 1)
        grid1.addWidget(label14a, 3, 0)
        grid1.addWidget(label14b, 3, 1)
        grid1.addWidget(label15a, 4, 0)
        grid1.addWidget(label15b, 4, 1)
        grid1.addWidget(label16a, 5, 0)
        grid1.addWidget(label16b, 5, 1)
        grid1.addWidget(label17a, 6, 0)
        grid1.addWidget(label17b, 6, 1)
        grid1.addWidget(label18a, 7, 0)
        grid1.addWidget(label18b, 7, 1)

        grid2 = QGridLayout()
        x = "- How to change these parameters: \n" \
            "•  Update lines 12-17 of 'gui_GMX500.py' as needed. "
        howlabel2 = QLabel(x)
        howlabel2.setWordWrap(True)

        layout2.addLayout(grid2)
        layout2.addWidget(howlabel2)

        label21a = QLabel("•  Local data storage folder: ")
        label21b = QLabel(LOCAL_DATA_PATH)
        label22a = QLabel("•  GUI refresh time: ")
        label22b = QLabel("%s s" % GUI_REFRESH_TIME)
        label23a = QLabel("•  Wind rose plot time window: ")
        label23b = QLabel("%s min" % PLOT_WINDOW_WIND)
        label24a = QLabel("•  Battery voltage plot time window: ")
        label24b = QLabel("%s h" % PLOT_WINDOW_V)
        label25a = QLabel("•  Delete data taken earlier than: ")
        label25b = QLabel("%s month" % MONTH)

        grid2.addWidget(label21a, 0, 0)
        grid2.addWidget(label21b, 0, 1)
        grid2.addWidget(label22a, 1, 0)
        grid2.addWidget(label22b, 1, 1)
        grid2.addWidget(label23a, 2, 0)
        grid2.addWidget(label23b, 2, 1)
        grid2.addWidget(label24a, 3, 0)
        grid2.addWidget(label24b, 3, 1)
        grid2.addWidget(label25a, 4, 0)
        grid2.addWidget(label25b, 4, 1)

        # right part
        image1 = QLabel()
        pixmap = QPixmap("icons/gill.png")
        image1.setPixmap(
            pixmap.scaled(
                550,
                300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        image1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label_image = QLabel("Wind Direction Diagram")
        label_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fig = plt.figure(figsize=(3, 3), linewidth=1)
        mathText = r'$ {Wind\/speed} = \sqrt{ {(u-axis\/\/velocity)}^2 + {(v-axis\/\/velocity)}^2 }$'
        #plt.rc('font', weight='bold', size=13)
        #plt.rcParams["mathtext.fontset"] = "dejavuserif"
        fig.text(.0, .3, mathText, fontsize = 13)
        canvas = FigureCanvas(fig)

        image2 = QLabel()
        pixmap = QPixmap("icons/GPS.png")
        image2.setPixmap(
            pixmap.scaled(
                250,
                250,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        image2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        label2_image = QLabel("GPS Diagram")
        label2_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rightlayout.addWidget(image1, 45)
        rightlayout.addWidget(label_image, 5)
        rightlayout.addWidget(canvas, 15)
        rightlayout.addWidget(image2, 30)
        rightlayout.addWidget(label2_image, 5)


    ## functions
    # delete files saved 3 months ago
    def delete_folders(self):
        folders = [name for name in os.listdir(LOCAL_DATA_PATH) if os.path.isdir(os.path.join(LOCAL_DATA_PATH, name))]
        folders.sort()
        # print(folders)
        epoch1 = int(time.mktime(time.strptime(folders[0], "%Y%m%d")))
        epoch_now = int(time.time())
        if (epoch_now - epoch1) > 2628000 * MONTH:  # seconds
            note = "! There are wind data older than %s months\nin the folder '%s'.\nPress Ok to delete these files and save disk space.\nPress Cancel to keep them (not recommended)." % (MONTH, LOCAL_DATA_PATH)

            reply = QMessageBox.question(
                self,
                "Warning",
                note,
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Ok,
                )

            if reply == QMessageBox.StandardButton.Ok:
                for name in folders:
                    epoch1 = int(time.mktime(time.strptime(name, "%Y%m%d")))
                    if (epoch_now - epoch1) > 2628000 * MONTH:
                        shutil.rmtree(os.path.join(LOCAL_DATA_PATH, name))
                        print('Delete folder: ', name)
                    else:
                        break
            else:
                print("keep files.")
                
                
    # battery voltage time series plot
    def plot_v(self, epoch_time, v):
        self.figure1.clear()
        ax1 = self.figure1.add_subplot(111)
        box = ax1.get_position()
        box.x0 = box.x0 + 0.04
        box.x1 = box.x1 + 0.05
        box.y0 = box.y0 - 0.01
        box.y1 = box.y1 + 0.05
        ax1.set_position(box)
        ax1.plot(epoch_time, v, marker = ".", color = "black", linewidth = 0.7)
        ax1.grid(alpha = 0.3)

        # axis label
        ax1.set_xlabel("Local Clock Time: %s" % (time.strftime("%Y-%m-%d")))
        ax1.set_ylabel("Battery Voltage, V", fontsize=10)

        # add mark for every half hour
        xx = [epoch_time[0]]
        xmak = [time.strftime('%H:%M', time.localtime(epoch_time[0]))]
        for i in range(1, len(epoch_time)):
            t = epoch_time[i]
            clock0 = time.strftime('%H:%M', time.localtime(epoch_time[i-1]))
            clock =  time.strftime('%H:%M', time.localtime(t))
            # print(clock0, clock)
            if (clock0[:2] != clock[:2]) or (int(clock0[-2:]) <= 29 and int(clock[-2:]) >= 30):
                xx.append(int(t))
                xmak.append(time.strftime('%H:%M', time.localtime(t)))       
                
        # print("xx: ", xx)
        # print("xmak: ", xmak)
        ax1.set_xticks(xx)
        ax1.set_xticklabels(xmak, fontsize=8)


    # real time display and plot
    def plot_voltage(self):
        try:
            n = os.path.getsize(TEMP_FILE_V)
            if n:
                data = np.genfromtxt(TEMP_FILE_V, delimiter=',')  # epoch, voltage
                # print(data)
                # this line produces warning, is suppressed
            else:
                data= []

            if data.size:
                epoch_time = data[:, 0]
                v = data[:, 1]
                
                v1 = v[-1]
                self.voltageLabel.setText(str(v1))
                # check if battery is dead
                if v1 < VOLTAGE_MIN:
                    b = 0
                    x = "! Warning, battery is dead: %s" % time.ctime()
                    try:
                        with open(self.warning_msg, 'a') as f:
                            f.write(x)
                    except:
                        pass
                    print(x)
                
                    if b != self.battery_state:
                        self.batteryLabel.setText("Battery is dead!")
                        self.battery_state = 0
                        self.voltageLabel.setStyleSheet(style.red1())
                else:
                    b = 1
                    if b != self.battery_state:
                        self.batteryLabel.setText("")
                        self.battery_state = 1
                        self.voltageLabel.setStyleSheet(style.green1())

                self.plot_v(epoch_time, v)
                self.canvas1.draw()
        except:
            print("battery plot failed")

    def plot_wind(self):
        try:
            n = os.path.getsize(TEMP_FILE_WIND)
            if n:
                data = np.genfromtxt(TEMP_FILE_WIND, delimiter=',')  # wind_dir, wind_speed
                # this line produces warning, is suppressed
            else:
                data= []

            if data.size:
                wind_dir = data[:, 0]
                wind_speed = data[:, 1]

                # windrose plot
                self.figure2.clear()
                rect = [0.1, 0.2, 0.8, 0.7]
                ax = WindroseAxes(self.figure2, rect)
                self.figure2.add_axes(ax)

                ax.bar(wind_dir, wind_speed, normed=True, opening=0.8, edgecolor='white')
                ax.set_legend(title='Wind Speed in m/s', bbox_to_anchor=(-0.1, -0.27))
                self.canvas2.draw()

                # real time values
                self.windSpeedLabel.setText(str(wind_speed[-1]))
                self.windDirLabel.setText(str(wind_dir[-1]))
                self.hintLabel.setText(self.startText + "Real time display...")

        except:
            self.hintLabel.setText(self.startText + " !Real time display failed.")

    def reportProgress(self, x):
        self.filename = x  # 20240712_14

    def runLongTask(self):
        # Step 2: Create a QThread object
        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = Worker()
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.reportProgress)
        # Step 6: Start the thread
        self.thread.start()


    def start(self):
        # error check
        tag = self.port_detect()
        if not tag:
            self.hintLabel.setText(" ! Anemometer is not connected.")

        if tag:
            self.rdrive_folder = self.folderLineEdit.text()
            if os.path.isdir(self.rdrive_folder):
                with open("par1/rdrive.txt", "w") as f:
                    f.write(self.rdrive_folder)
            else:
                self.hintLabel.setText("! Folder to store data does not exist.")
                tag = 0
                
            self.warning_msg = os.path.join(self.rdrive_folder, "battery_warning.txt")
            if os.path.isfile(self.warning_msg):
                os.remove(self.warning_msg)

        if tag:
            try:
                self.runLongTask()
                print('running long task')
                time.sleep(3)
                
                # initiate battery plot: battery plot updated less (every few minutes)
                # than wind plot, so display values on GUI at the beginning.
                data = np.genfromtxt(TEMP_FILE_V, delimiter=',')
                epoch_time = data[:, 0]
                v = data[:, 1]
                v1 = v[-1]
                self.voltageLabel.setText(str(v1))
                self.plot_v(epoch_time, v)
                self.canvas1.draw()
                
                self.battery_state = 1  # 1: normal, 0: dead
                self.timer_plot.start()
                self.timer_battery.start()

                self.StartButton.setEnabled(False)
                self.ClearButton.setEnabled(True)
                self.StopButton.setEnabled(True)
                self.startText = "Started at: %s. " % time.strftime("%Y-%m-%d %H:%M:%S")
                self.hintLabel.setText(self.startText)
            except:
                self.hintLabel.setText(" ! Error start.")


    def stop(self):
        filename = time.strftime("%Y%m%d_%H")
        global stoprun
        stoprun = 1

        self.timer_plot.stop()
        self.timer_battery.stop()

        self.StartButton.setEnabled(True)
        self.ClearButton.setEnabled(False)
        self.StopButton.setEnabled(False)

        # copy last file to R drive
        file_path = os.path.join(LOCAL_DATA_PATH, filename[:8], filename + ".csv")
        r_folder_path = os.path.join(self.rdrive_folder, filename[:8])
        try:
            shutil.copy2(file_path, r_folder_path)  # source, destination
        except:
            print("copy last file to r-drive failed: %s.csv" % filename)

        self.hintLabel.setText("Stopped at: %s. " % time.strftime("%Y-%m-%d %H:%M:%S"))


    def clear_plots(self):
        global clearplot
        clearplot = 1


    def brouse_folder(self):
        folder = QFileDialog.getExistingDirectory()
        self.folderLineEdit.setText(folder)

    def port_get(self):
        PORTLIST = [p.device for p in ls.comports()]
        print(PORTLIST)
        self.portComboBox.clear()
        self.portComboBox.addItems(PORTLIST)

    def port_detect(self):
        port = self.portComboBox.currentText()
        wind = serial.Serial(port, BAUDRATE, timeout = 5)
        x = wind.readline().decode()
        if x:
            with open("par1/port.txt", "w") as f:
                f.write(port)
            self.portHintLabel.setText("\u2713")
            print("Anemometer connected.")
            # print(x)
            return 1
        else:
            self.portHintLabel.setText("\u2717")
            print("Anemometer NOT connected.")
            return 0


def main():
    app = QApplication(sys.argv)
    window = Window()
    app.setWindowIcon(QIcon("icons/p2.jpeg"))
    window.show()
    app.exec()


if __name__ == "__main__":
    main()



# @author: Yilin Shi | 2024.10.10
# shiyilin890@gmail.com
# Bog the Fat Crocodile vvvvvvv
#                       ^^^^^^^
