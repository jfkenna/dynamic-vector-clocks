from mpi4py import MPI
import numpy
from datetime import datetime
import random
from time import sleep
import sys

# MPI World Setup (Lafayette 2021) (Dalcin 2020).
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

# Local process variables
message_queue = []

def main():
    vector_arr = numpy.zeros((nproc, nproc))

    ops_list = [
        "s1, a", #Process 1
        "r1, r2", #Process 2
        "s2, b" #Process 3
    ]

    if iproc == 0:
        print("Process {0} to deconstuct ops @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        sleep(2)
        for i in range(1, nproc):
            print("Process {0} sending ops to {1} @ {2} seconds".format(
                iproc, 
                i,
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))
            comm.send(i, dest=i, tag=0)
    else:
        print("Process {0} @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        data = comm.recv(source=0, tag=0)
        print("Process {0} got some data from root @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))

def randoms():
    vector_arr = numpy.zeros((nproc, nproc))
    if iproc == 0:
        vector_arr[iproc][0] = 1
        print(vector_arr)
        print("Root process @ {0}".format(str(datetime.now().strftime("%H:%M:%S.%f"))))
        for i in range(1, nproc):
            vector_arr_recv = comm.recv(source=i, tag=0)
            print("Process 0 received V.A from process {0}".format(i))
            print(vector_arr_recv)
    else:
        sleeper = random.uniform(0, 10)
        print("Process {0} decided at {1} to sleep for {2} seconds".format(
            iproc, 
            datetime.now().strftime("%H:%M:%S.%f"), 
            sleeper
        ))
        sleep(sleeper)
        # Increment vector array at index 0
        vector_arr[iproc][0] = 1
        print("Process {0} sending @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        comm.send(vector_arr, dest=0, tag=0)

main()

'''
Refs
https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds 13th March
https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range 15th March
https://numpy.org/doc/stable/reference/generated/numpy.zeros.html 16th March
https://nyu-cds.github.io/python-mpi/03-nonblocking/#:~:text=In%20MPI%2C%20non%2Dblocking%20communication,uniquely%20identifys%20the%20started%20operation. 24th March
'''
