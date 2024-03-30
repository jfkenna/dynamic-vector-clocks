from mpi4py import MPI
import numpy
from datetime import datetime
import random
from time import sleep
import sys
import re

# MPI World Setup (Lafayette 2021) (Dalcin 2020).
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

# Local process variables
message_queue = []

def process_loop(process_ops):
    print("Process loop: {0}".format(iproc))
    print(process_ops)
    for op in process_ops:
        print("Operation:", op)
        recv_op = re.search("^r([1-9].*)", op) # If the event was a receive
        send_op = re.search("^s([1-9].*)", op) # If the event was a send
        internal_op = re.search("^([a-zA-Z].*)", op) # If the event was internal
        if recv_op:
            print("Receive with tag:", recv_op.group(1))
        elif send_op:
            print("Send with tag:", send_op.group(1))
        elif internal_op:
            print("An internal op:", internal_op.group(0))
        """
        # Send event
        elif re.match("^s([1-9].*)", op):
           print("Send event:", op)
        # Any other internal event
        elif re.match("^([a-zA-Z].*)", op):
            print( "Internal event:", op)
        """


def main():
    vector_arr = numpy.zeros((nproc, nproc))

    ops_list = [
            "s1, a", #Process 1
            "r1", #Process 2
    ]

    if iproc == 0:
        print("Process {0} to deconstuct ops @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        sleep(2)
        for i in range(0, nproc-1):
            print("Process {0} -> {1}".format(i, ops_list[i]))
            print("Process {0} sending ops to {1} @ {2} seconds".format(
                iproc, 
                i+1, #Sending to i+1
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))
            #print(ops_list[i])
            comm.send(ops_list[i], dest=i+1, tag=0)
            print("\n")

        # Await until each process has finished and sent a confirmation back
            
    else:
        print("Process {0} @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        data = comm.recv(source=0, tag=0)
        process_ops = data.split(", ")
        print("Process {0} got some data from root @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        process_loop(process_ops)
        print("\n")

        


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
https://www.w3schools.com/python/ref_string_split.asp 30th March
https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ 30th March
https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 30th March
https://www.tutorialsteacher.com/regex/grouping 30th March
https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match 30th March
'''
