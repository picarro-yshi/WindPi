import sys
import platform
import time
import os
import numpy as np
import pandas as pd

import serial
import socket
PORT = '/dev/ttyUSB2'
BAUDRATE = 19200
DATA_PATH = '/mnt/r/crd_G9000/AVXxx/3610-NUV1022/R&D/roofwind/data'
DATA_REFRESH_TIME = 2  # s

import serial.tools.list_ports as ls
print([p.device for p in ls.comports()])

opsystem = platform.system()  # 'Linux', 'Windows', 'Darwin'
print(opsystem)
print(platform.node())  # hostname
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
    )
    from PyQt6.QtCore import QObject, QThread
    from PyQt6.QtCore import pyqtSignal as Signal


from matplotlib import pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

import style

global stoprun  # 1 stop thread, 0 keep running


# Step 1: Create a worker class
class Worker(QObject):
    finished = Signal()
    # progress = Signal(int)
    progress = Signal(str)

    def run(self):
        """Long-running task."""
        global stoprun
        stoprun = 0

        # for i in range(20):
        #     if stoprun:
        #         break
        #     sleep(1)
        #     self.progress.emit(i + 1)

        wind = serial.Serial(PORT, BAUDRATE)
        print(wind.name)

        start_time = time.time()
        now_time = time.strftime("%Y%m%d_%H%M%S")
        data_path = os.path.join(DATA_PATH, now_time + ".csv")
        with open(data_path, "w") as f:
            f.write("epoch_time, clock_time,U_speed_NS,V_speed_WE\n")

        while True:
            if stoprun:
                break

            now = time.time()
            now_time = time.strftime("%Y%m%d_%H%M%S")

            if now - start_time > 3600:  # a new csv every hour
                data_path = os.path.join(DATA_PATH, now_time + ".csv")
                with open(data_path, "w") as f:
                    f.write("epoch_time, clock_time,U_speed_NS,V_speed_WE\n")
                start_time = now
                self.progress.emit(now_time)

            x = wind.readline().decode()
            y = x.split(',')
            u = float(y[1])  # u axis speed, NS
            v = float(y[2])  # v axis speed, WE

            with open(data_path, "a") as f:
                f.write("%s,%s,%s,%s\n" % (now, now_time, u, v))

        self.finished.emit()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(200, 200, 1200, 800)
        self.setWindowTitle("Picarro R&D")
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
        topLayout = QHBoxLayout()
        bottomLayout = QHBoxLayout()
        mainLayout.addLayout(topLayout, 10)
        mainLayout.addLayout(bottomLayout, 90)

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

        leftLayout = QVBoxLayout()
        rightLayout = QVBoxLayout()

        # box1 = QGroupBox("Local Computer")
        # box1.setStyleSheet(style.box1())
        # box1.setLayout(self.transferLayout)

        # box2 = QGroupBox("Local Instrument")
        # box2.setStyleSheet(style.box2())
        # box2.setLayout(self.instrumentLayout)
        #
        # mainLayout.addWidget(titleLabel, 5)
        # mainLayout.addWidget(box1, 45)
        # mainLayout.addWidget(box2, 50)

        bottomLayout.addLayout(leftLayout)
        bottomLayout.addLayout(rightLayout)

        self.Layout = QHBoxLayout()
        #leftLayout.addLayout(self.Layout)

        
        # time plot
        self.figure1 = plt.figure()
        self.canvas1 = FigureCanvas(self.figure1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        self.toolbar1.setFixedHeight(30)

        leftLayout.addWidget(self.canvas1)
        leftLayout.addWidget(self.toolbar1)
        leftLayout.addLayout(self.Layout)

        # windrose plot
        
        self.figure2 = plt.figure()
        self.canvas2 = FigureCanvas(self.figure2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        self.toolbar2.setFixedHeight(30)

        rightLayout.addWidget(self.canvas2)
        rightLayout.addWidget(self.toolbar2)
        

        self.createLayout1()
        self.createLayout2()

        self.setLayout(mainLayout)

        self.timer_plot = QTimer()
        self.timer_plot.setInterval(DATA_REFRESH_TIME * 1000)
        # self.timer_plot.timeout.connect(lambda: greeter_server.scale_plot(self))
        self.timer_plot.timeout.connect(self.plot_wind)



    def createLayout1(self):
        layout1 = QVBoxLayout()
        layout2 = QVBoxLayout()
        self.Layout.addLayout(layout1)
        self.Layout.addLayout(layout2)

        self.StartButton = QToolButton()
        self.StartButton.setIcon(QIcon("icons/start1.png"))
        self.StartButton.setIconSize(QSize(40, 40))
        self.StartButton.clicked.connect(self.start)
        # self.StartButton.clicked.connect(lambda: func_experiment.start_exp(self))
        # self.StartButton.setEnabled(False)
        label1 = QLabel("   Start")
        label1.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout1.addWidget(self.StartButton)
        layout1.addWidget(label1)

        self.StopButton = QToolButton()
        self.StopButton.setIcon(QIcon("icons/stop1.png"))
        self.StopButton.setIconSize(QSize(40, 40))
        self.StopButton.clicked.connect(self.stop)
        self.StopButton.setEnabled(False)
        label2 = QLabel("   Stop")
        label2.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout2.addWidget(self.StopButton)
        layout2.addWidget(label2)


    def createLayout2(self):
        pass

    def plot_wind(self):
        # print('plot', self.filename)

        # time series
        self.figure1.clear()
        ax1 = self.figure1.add_subplot(111)

        data_path = os.path.join(DATA_PATH, self.filename + ".csv")
        df = pd.read_csv(data_path)
        wind_u = df["NS_speed"]
        wind_v = df["WE_speed"]
        time = df["epoch_time"]

        if df.shape[0] > 240:
            wind_u = wind_u[:240]
            wind_v = wind_v[:240]
            time = time[:240]

        wind_speed = np.sqrt(wind_u ** 2 + wind_v ** 2)

        # plt.figure()
        # plt.quiver(time, wind_speed, wind_u, wind_v)
        # plt.show()

        ax1.quiver(time, wind_speed, wind_u, wind_v)
        self.canvas1.draw()

        # windrose
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

        wind_dir = wind_uv_to_dir(wind_u, wind_v)




    def reportProgress(self, n):
        # self.stepLabel.setText(f"Long-Running Step: {n}")
        self.filename = n
        print(n)

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

        # Final resets
        # self.StartButton.setEnabled(False)
        # self.StopButton.setEnabled(True)
        # self.thread.finished.connect(
        #     lambda: self.StartButton.setEnabled(True)
        # )
        # self.thread.finished.connect(
        #     lambda: self.stepLabel.setText("Long-Running Step: 0")
        # )


    def start(self):
        self.runLongTask()
        self.timer_plot.start()
        self.filename = time.strftime("%Y%m%d_%H%M%S")

        self.StartButton.setEnabled(False)
        self.StopButton.setEnabled(True)
        print('Record started.')



    def stop(self):
        global stoprun
        stoprun = 1

        self.timer_plot.stop()
        self.StartButton.setEnabled(True)
        self.StopButton.setEnabled(False)
        print('Record stopped.')




def main():
    app = QApplication(sys.argv)
    window = Window()
    app.setWindowIcon(QIcon("icons/p2.jpeg"))
    window.show()
    app.exec()


if __name__ == "__main__":
    main()



# @author: Yilin Shi | 2024.4.25
# shiyilin890@gmail.com
# Bog the Fat Crocodile vvvvvvv
#                       ^^^^^^^

