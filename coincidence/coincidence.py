# Front Panel for coincidence detection
# Written by Alessandro Restelli (JQI) Fall 2023

import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, clear_output
from matplotlib.widgets import Button,CheckButtons,TextBox
import serial


class Controls:
    """This class is used to interact with the hardware.
    collect_data is a generator that handles the data request from hardware as
    well as writing on an output file.

    It also contains and modifies logic states that keep
    track of asynchronous events such as key presses etc...

    """
    def __init__(self,hardware_name='COM5',filename=None, append = True):
        self.filename=filename
        if not (self.filename==None):
            self.file = open(filename,"a" if append else 'w')
        self.keep_running = True
        self.t = 0
        self.ser = serial.Serial(hardware_name,baudrate=115200)  # open serial port
        print(self.ser.name)  
        print("FPGA hardware initialized")

    def write_file(self,data):
            self.file.writelines([f"{data}\n"])

    def stop_pressed(self,handle):
        self.keep_running = False

    def collect_data(self,samples=-1):
        """ collects "samples" samples from FPGA. or if "samples" < 0 it keeps collecting data until
            Controls.keep_running is set to False. This can be done with the stop_pressed(handle) method
            that can be called, for example by a button widget.
        """
        self.ser.write(b's')
        print("The FPGA is started the acquisition")
        while self.keep_running and (samples != 0):
            if samples > 0:
                samples-=1
            #Code that collects data drom the hardware
            data = [float(np.frombuffer(self.ser.read(4)[::-1],dtype=np.uint32)) for _ in range(7) ]
            if not (self.filename == None):
                self.write_file(data)
            yield data
        if not (self.filename==None):
            self.file.close()
            
        self.ser.write(b'x')
        print("The FPGA is stopped the acquisition")


class DataChart:
    """This class creates an datachart.
    A datachart creates a plot and scrolls the content.
    At the same time it keeps track of time and saves the sum of all
    samples. Useful fields are:
        datachart.sum
        datachart.data
        datachart.title
        datachart.time
    """
    def __init__(self,fig,gridspec,title="Test",interval=60,delta_t=1.0):
        self.ax = fig.add_subplot(gridspec)
        self.samples = int(interval/delta_t)
        self.interval = self.samples*delta_t
        self.delta_t = delta_t
        self.t_buffer = np.linspace(0,interval,self.samples)
        self.data_buffer = np.zeros(self.samples)
        self.index = 0
        self.time = 0
        self.data = 0
        self.sum = 0
        self.plot = self.ax.plot(self.time,self.data)[0]
        plt.title(title)
        self.title = title
        self.ax.set_autoscale_on(True)
        
    def update(self,data):
        self.data=data
        t = self.time
        if self.index==self.samples:
            self.t_buffer[:-1] = self.t_buffer[1:]
            self.data_buffer[:-1] = self.data_buffer[1:]
            self.index=self.index-1
        self.t_buffer[self.index] = t   
        self.data_buffer[self.index] = data
        self.plot.set_xdata(self.t_buffer[:self.index+1])
        self.plot.set_ydata(self.data_buffer[:self.index+1])
        self.ax.relim()
        self.ax.autoscale_view(True,True,True)
        self.time+=self.delta_t
        self.ax.set_xlim(self.t_buffer[-1]-self.interval, self.t_buffer[-1] ,self.samples)
        self.index = min(self.index+1,self.samples)
        self.sum+=data


def run_gui(initial_tau=[3.85e-9,2.65e-9,3.6e-9]):

    #This part of the program automatically finds the COM port
    # It simply selects the last port found.
    # This behavior should always work since typically the COM port used by the FPGA
    #  is the last of the list, however a more soffisticated search could be implemented
    #  if this does not work.
    
    import serial.tools.list_ports
    com_port = serial.tools.list_ports.comports()[-1].device
    
    #This line initializes the hardware and selects the output file.
    controls = Controls(hardware_name = com_port, filename = "./output.txt", append = True)
    
    #This sets up the figure as both visualization and control panel.
    # GridSpec is an advanced framing system that allows to place plots
    # and widgets in a "quantized" grid by specifying ranges

    fig = plt.figure(figsize=(8, 6))
    grid = plt.GridSpec(4, 4, hspace=0.5, wspace=0.5)

    # Placement of all the plots in a grid

    A = DataChart(fig,          grid[0, 1],     title="A",)
    B = DataChart(fig,          grid[0, 2],     title="B")
    B_prime = DataChart(fig,    grid[0, 3],     title="B'")
    AB = DataChart(fig,         grid[1, 1],     title="AB")
    AB_prime = DataChart(fig,   grid[1, 2],     title="AB'")
    BB_prime = DataChart(fig,   grid[1, 3],     title="BB'")
    ABB_prime = DataChart(fig,  grid[2, 3],     title="ABB'")


    # Placement of empty plot for text elements (Numerical values)
    text = fig.add_subplot(grid[:, 0])
    text.get_xaxis().set_visible(False)
    text.get_yaxis().set_visible(False)

    # This section places widgets such as buttons and check buttons

    #This is the STOP button
    button = Button(fig.add_subplot(    grid[2, 1]  ),"STOP")
    button.on_clicked(controls.stop_pressed)

    #These are the check marks to enable or not the accidental correction and the vector
    # containing the estimation of the coincidence window
    checks = CheckButtons(fig.add_subplot(  grid[2, 2]  ), ["AB","AB'","BB'"])
    text_box = TextBox(fig.add_subplot(     grid[3, 2]  ), "[AB, AB, BB'] = ", initial = initial_tau)


    # Now that we have defined all graphical elements we can display the panel
    display(fig)


    # The main loop iterates through the collected data.
    for data in controls.collect_data():
        
        #This section applies the correction for accidental counts
        # The correction will not be saved on the raw output file but
        # it will affect the "total counts" visualized on the graphical panel 
        AB_correct, AB_prime_correct, BB_prime_correct = checks.get_status()
        try:
            # n+3 gives the index 3,4,5 that are correspondent to AB, AB_prime, BB_prime.
            tau = eval(text_box.text)
            if len(tau)!=3:
                tau = initial_tau
        except:
            #This prevents partially written data to be evaluated incorrectly
            pass
        
        if AB_correct:
            data[3] = data[3] - data[0] * data[1] * 2 * tau [0]
        
        if AB_prime_correct:
            data[4] = data[4] - data[0] * data[2] * 2 * tau [1]
        
        if BB_prime_correct:
            data[5] = data[5] - data[1] * data[2] * 2 * tau [2]

        #This section updates the plots and text elements
        text.cla() #the text needs to be cleared before being updated
        for n, plot in enumerate([A, B, B_prime, AB, AB_prime, BB_prime, ABB_prime]):
                            #Note: this ^ list reflects the exact order of data in the binary frame                                                                         
            plot.update(data[n])
            text.text(0.05,1/7*((6-n)+0.5), "{:<4} {:.0f} {:.0f}".format(plot.title,plot.data,plot.sum),size=14)
        fig.canvas.flush_events()
        plt.pause(0.01) #Without this line the graphical system does not have time to draw.
    controls.ser.close()
if __name__=="__main__":
    run_gui()
    
