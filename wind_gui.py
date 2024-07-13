# wind anemometer data recorder control code
#####  default setting parameters  #####
## anemometer
BAUDRATE = 19200
DATA_RATE = 4  # Hz, data output rate
## GUI
LOCAL_DATA_PATH = "/home/picarro/Wind_data"  # folder to save data locally
GUI_REFRESH_TIME = 2  # s
PLOT_WINDOW = 5  # min, time length for GUI data display
HEADER = "epoch_time,local_clock_time,U_velocity_NS,V_velocity_WE,speed,direction\n"  # csv header

import sys
import platform
import os
import shutil
import time
from datetime import datetime
import numpy as np
import pandas as pd

import serial
import serial.tools.list_ports as ls

opsystem = platform.system()  # 'Linux', 'Windows', 'Darwin'
print(opsystem)
print("hostname: ", platform.node())

## Qt GUI
if 'rasp' in platform.node():  # on a raspberry pi, use PySide6
    from PySide6.QtGui import QPixmap, QIcon, QAction
    from PySide6.QtCore import Qt, QTimer, QSize
    from PySide6.QtWidgets import (
        QApplication,
        QTabWidget,
        QPushButton,
        QMessageBox,
        QTableWidget,
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
        QTableWidgetItem,
        QScrollArea,
        QToolBar,
        QMainWindow,
        QFileDialog,
    )
    from PySide6.QtCore import QObject, QThread, Signal

else:
    # use PyQt6
    from PyQt6.QtGui import QPixmap, QIcon, QAction
    from PyQt6.QtCore import Qt, QTimer, QSize
    from PyQt6.QtWidgets import (
        QApplication,
        QTabWidget,
        QPushButton,
        QMessageBox,
        QTableWidget,
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
        QTableWidgetItem,
        QScrollArea,
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


def wind_uv_to_dir(U, V):
    """
    Calculates the wind direction from the u and v component of wind.
    Takes into account the wind direction coordinates is different than the
    trig unit circle coordinate. If the wind directin is 360 then returns zero
    (by %360)
    Inputs:
      U = west/east direction (wind from the west is positive, from the east is negative)
      V = south/noth direction (wind from the south is positive, from the north is negative)
    """
    WDIR = (270 - np.rad2deg(np.arctan2(V, U))) % 360
    return WDIR


# Step 1: Create a worker class
class Worker(QObject):
    finished = Signal()
    progress = Signal(str)

    def run(self):
        """Long-running task."""
        global stoprun
        stoprun = 0

        with open("par1/port.txt", "r") as f:
            PORT = f.read()  # '/dev/ttyUSB2'

        with open("par1/rdrive.txt", "r") as f:
            rdrive_path = f.read()

        wind = serial.Serial(PORT, BAUDRATE)
        print('anemometer USB port: ', wind.name)

        filename = time.strftime("%Y%m%d_%H")
        self.progress.emit(filename)

        # create folder of the day on local drive
        folder_path = os.path.join(LOCAL_DATA_PATH, filename[:8])
        if not os.path.isdir(folder_path):
            os.mkdir(folder_path)

        file_path = os.path.join(folder_path, filename + ".csv")
        with open(file_path, "w") as f:
            f.write(HEADER)

        # create folder of the day on r-drive
        rdrive_folder = os.path.join(rdrive_path, filename[:8])
        if not os.path.isdir(rdrive_folder):
            os.mkdir(rdrive_folder)

        while True:
            if stoprun:
                break

            epoch = time.time()
            # use pandas library default time format, to ms
            clock_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            now = time.strftime("%Y%m%d_%H")  # 20240712_14

            # create a new folder every day
            if (now[-2:] == 0) and (filename[-2:] == 23):
                # locally
                folder_path = os.path.join(LOCAL_DATA_PATH, now[:8])
                os.mkdir(folder_path)

                # on r-drive
                rdrive_folder = os.path.join(rdrive_path, now[:8])
                os.mkdir(rdrive_folder)

            # create a new csv every hour and copy to r-drive
            if now[-2:] != filename[-2:]:
                # copy previous hour csv to r-drive
                while True:
                    try:
                        shutil.copy2(file_path, rdrive_folder)  # source, destination
                        break
                    except:
                        print("copy to r-drive failed: %s.csv" % filename)

                filename = now
                file_path = os.path.join(folder_path, filename + ".csv")
                with open(file_path, "w") as f:
                    f.write(HEADER)
                self.progress.emit(filename)

            x = wind.readline().decode()
            y = x.split(',')
            u = float(y[1])  # u axis speed, NS
            v = float(y[2])  # v axis speed, WE

            wind_speed = np.sqrt(u ** 2 + v ** 2)
            wind_dir = wind_uv_to_dir(u, v)

            with open(file_path, "a") as f:
                # need a space before clock time so excel reads it as string
                f.write("%s, %s,%s,%s,%s,%s\n" % (epoch, clock_time, u, v,wind_speed,wind_dir))

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

        titleLabel = QLabel("Real Time Wind Data Recorder")
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
        figure1Layout.setContentsMargins(20, 30, 20, 10)
        box1 = QGroupBox(" Time Series Plot")
        box1.setStyleSheet(style.box1())
        box1.setLayout(figure1Layout)

        self.Layout = QVBoxLayout()
        leftLayout.addWidget(box1)
        leftLayout.addLayout(self.Layout)

        # tab1 right part
        figure2Layout = QVBoxLayout()
        figure2Layout.setContentsMargins(20, 30, 20, 10)
        box2 = QGroupBox(" Wind Rose Plot")
        box2.setStyleSheet(style.box2())
        box2.setLayout(figure2Layout)
        rightLayout.addWidget(box2)

        # time plot
        self.figure1 = plt.figure()
        self.canvas1 = FigureCanvas(self.figure1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        self.toolbar1.setFixedHeight(30)

        figure1Layout.addWidget(self.canvas1)
        figure1Layout.addWidget(self.toolbar1)

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

        # timer
        self.timer_plot = QTimer()
        self.timer_plot.setInterval(GUI_REFRESH_TIME * DATA_RATE * 1000)
        self.timer_plot.timeout.connect(self.plot_wind)


    def createLayout1(self):  # tab1
        layout1 = QHBoxLayout()
        layout2 = QHBoxLayout()
        bottomLayout = QHBoxLayout()
        self.Layout.addLayout(layout1)
        self.Layout.addLayout(layout2)
        self.Layout.addLayout(bottomLayout)

        # line 1
        label11 = QLabel("Wind Velocity (m/s):")
        label12 = QLabel("U-axis (NS):")
        label12.setToolTip("South - North")
        label12.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.uLabel = QLabel()
        self.uLabel.setStyleSheet(style.grey1())
        self.uLabel.setFixedHeight(24)

        label13 = QLabel("V-axis (WE):")
        label13.setToolTip("East - West")
        label13.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.vLabel = QLabel()
        self.vLabel.setStyleSheet(style.grey1())
        self.vLabel.setFixedHeight(24)

        layout1.addWidget(label11)
        layout1.addWidget(label12)
        layout1.addWidget(self.uLabel)
        layout1.addWidget(label13)
        layout1.addWidget(self.vLabel)

        # line 2
        label21 = QLabel("Folder:")
        self.folderLineEdit = QLineEdit("")
        self.folderLineEdit.setToolTip("R drive folder path to store data:")
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
        stopButtonLayout = QVBoxLayout()

        bottomLayout.addLayout(layout3, 70)
        bottomLayout.addLayout(startButtonLayout, 15)
        bottomLayout.addLayout(stopButtonLayout, 15)

        portLayout = QHBoxLayout()
        self.hintLabel = QLabel()
        self.hintLabel.setStyleSheet(style.grey1())
        self.hintLabel.setFixedHeight(30)

        layout3.addLayout(portLayout)
        layout3.addWidget(self.hintLabel)
        layout3.addStretch()

        portLabel = QLabel("Anemometer port:")
        portLabel.setToolTip("Serial-USB port name")
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
        startLabel = QLabel("  Start")
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


    def createLayout2(self):
        leftlayout = QVBoxLayout()
        rightlayout = QVBoxLayout()
        gap = QLabel()
        self.tab2Layout.addLayout(leftlayout, 48)
        self.tab2Layout.addWidget(gap, 2)
        self.tab2Layout.addLayout(rightlayout, 50)
        # self.tab2Layout.addStretch()

        # left part
        layout1 = QVBoxLayout()
        layout2 = QVBoxLayout()
        layout3 = QVBoxLayout()
        leftlayout.addLayout(layout1)
        leftlayout.addLayout(layout2)
        leftlayout.addLayout(layout3)
        leftlayout.addStretch()

        # anemometer settings
        titlelabel1 = QLabel("Anemometer default settings:")
        titlelabel1.setStyleSheet(style.headline3())

        grid1 = QGridLayout()
        x = "How to change the parameters: \n" \
            "Method1:\n find the commands in the 'manual.pdf'," \
            " update the first line in the 'setup.py' file and run it," \
            " power off then power on the anemometer" \
            " to reflect the change.\n" \
            "Method2:\n take the anemometer and connect to a Windows computer," \
            " ask John Yiu to help with changing the parameters.\n" \
            "Then update line 4-5 of 'wind_gui.py' if needed. "
        howlabel1 = QLabel(x)
        # howlabel1.setFixedWidth(500)
        howlabel1.setWordWrap(True)

        layout1.addWidget(titlelabel1)
        layout1.addLayout(grid1)
        layout1.addWidget(howlabel1)

        label11a = QLabel("Format: ")
        label11b = QLabel("U-axis velocity, V-axis velocity")
        label12a = QLabel("Data record speed: ")
        label12b = QLabel("4 Hz")
        label13a = QLabel("Unit: ")
        label13b = QLabel("m/s")

        grid1.addWidget(label11a, 0, 0)
        grid1.addWidget(label11b, 0, 1)
        grid1.addWidget(label12a, 1, 0)
        grid1.addWidget(label12b, 1, 1)
        grid1.addWidget(label13a, 2, 0)
        grid1.addWidget(label13b, 2, 1)

        # GUI settings
        titlelabel2 = QLabel("GUI default settings:")
        titlelabel2.setStyleSheet(style.headline3())

        grid2 = QGridLayout()
        x = "How to change the parameters: \n" \
            "Update line 6-9 of 'wind_gui.py' as needed. "
        howlabel2 = QLabel(x)
        # howlabel2.setFixedWidth(500)
        howlabel2.setWordWrap(True)


        layout2.addWidget(titlelabel2)
        layout2.addLayout(grid2)
        layout2.addWidget(howlabel2)

        label21a = QLabel("Local data storage folder: ")
        label21b = QLabel(LOCAL_DATA_PATH)
        label22a = QLabel("GUI refresh time: ")
        label22b = QLabel("%s s" % GUI_REFRESH_TIME)
        label23a = QLabel("GUI data display time window: ")
        label23b = QLabel("%s min" % PLOT_WINDOW)

        # LOCAL_DATA_PATH = '/home/picarro/Wind_data'  # folder to save data locally
        # GUI_REFRESH_TIME = 2  # s
        # PLOT_WINDOW = 5

        grid2.addWidget(label21a, 0, 0)
        grid2.addWidget(label21b, 0, 1)
        grid2.addWidget(label22a, 1, 0)
        grid2.addWidget(label22b, 1, 1)
        grid2.addWidget(label23a, 2, 0)
        grid2.addWidget(label23b, 2, 1)


        # right part
        label= QLabel("Wind speed = √(u-axis velocity^2 + v-axis velocity^2)")
        label.setStyleSheet(style.headline3())
        rightlayout.addWidget(label)



        # real time display and plot
    def plot_wind(self):
        try:
            # time series plot
            self.figure1.clear()
            ax1 = self.figure1.add_subplot(111)

            data_path = os.path.join(LOCAL_DATA_PATH, self.filename[:8], self.filename + ".csv")
            df = pd.read_csv(data_path)
            epoch_time = df["epoch_time"]
            wind_u = df["U_velocity_NS"]
            wind_v = df["V_velocity_WE"]
            wind_speed = df["speed"]
            wind_dir = df["direction"]

            n = PLOT_WINDOW * DATA_RATE * 60
            if df.shape[0] > n:
                epoch_time = epoch_time[-n:]
                wind_u = wind_u[-n:]
                wind_v = wind_v[-n:]
                wind_speed = wind_speed[-n:]
                wind_dir = wind_dir[-n:]

            ax1.quiver(epoch_time, wind_speed, wind_u, wind_v)

            # axis label
            ax1.set_xlabel("Local Clock Time: %s" % (time.strftime("%Y-%m-%d")))
            ax1.set_ylabel("Wind Speed, m/s", fontsize=10)

            # add mark for every minute
            xx = list(epoch_time[::DATA_RATE * 60])
            xmak = []
            for i in xx:
                a = time.strftime('%H:%M', time.localtime(i))
                xmak.append(a)
            ax1.set_xticks(xx)
            ax1.set_xticklabels(xmak, fontsize=8)

            self.canvas1.draw()

            # windrose plot
            self.figure2.clear()
            rect = [0.1, 0.2, 0.8, 0.7]
            ax = WindroseAxes(self.figure2, rect)
            self.figure2.add_axes(ax)

            ax.bar(wind_dir, wind_speed, normed=True, opening=0.8, edgecolor='white')
            ax.set_legend(title='Wind Speed in m/s', bbox_to_anchor=(-0.1, -0.3))
            self.canvas2.draw()

            # real time values
            self.uLabel.setText(str(wind_u.iloc[-1]))
            self.vLabel.setText(str(wind_v.iloc[-1]))

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
            self.folder_path = self.folderLineEdit.text()
            if os.path.isdir(self.folder_path):
                with open("par1/rdrive.txt", "w") as f:
                    f.write(self.folder_path)                    
            else:
                self.hintLabel.setText("! Folder to store data does not exist.")
                tag = 0


        if tag:
            try:
                self.runLongTask()
                self.timer_plot.start()

                self.StartButton.setEnabled(False)
                self.StopButton.setEnabled(True)
                # print('Record started.')
                self.startText = "Recording started at: %s. " % time.strftime("%Y-%m-%d %H:%M:%S")
                self.hintLabel.setText(self.startText)
            except:
                self.hintLabel.setText(" ! Error start.")



    def stop(self):
        global stoprun
        stoprun = 1

        self.timer_plot.stop()
        self.StartButton.setEnabled(True)
        self.StopButton.setEnabled(False)
        # print('Record stopped.')
        self.hintLabel.setText("Recording stopped at: %s. " % time.strftime("%Y-%m-%d %H:%M:%S"))


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



# @author: Yilin Shi | 2024.7.25
# shiyilin890@gmail.com
# Bog the Fat Crocodile vvvvvvv
#                       ^^^^^^^
