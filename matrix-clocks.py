from mpi4py import MPI
import numpy
from datetime import datetime
import random
from time import sleep
import sys
import re
import uuid

# MPI World Setup (Lafayette 2021) (Dalcin 2020).
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

# Local process variables
message_queue = []

def broadcast_message(message, event_tag):
    # Extract target processes (without root)
    target_idx = [x for x in range(1, nproc) if x != iproc]
    print("Process {0} broadcasting message to {1} @ {2} ".format(
        iproc, 
        target_idx,
        datetime.now().strftime("%H:%M:%S.%f"), 
    ))
    # Develop the vector clock here, knowing target proce
    for idx in target_idx:
        comm.send(message, dest=idx, tag=int(event_tag))

def determine_recv_process(ops_list, event_tag):
    target_event = "r" + event_tag
    print("Target event:", target_event)
    for idx in range(0, len(ops_list)):
        if target_event in ops_list[idx]:
            print("Send this event to process {0}".format(idx+1))
            return idx+1
        
def determine_sender_process(ops_list, event_tag):
    # Target events for sender processes
    target_event = "s" + event_tag
    target_bcast_event = "r" + event_tag
    print("Target events: {0},{1}".format(target_event, target_bcast_event))
    for idx in range(0, len(ops_list)):
        if target_event in ops_list[idx]:
            print("Received this event from process {0}".format(idx+1))
            return idx+1
        elif target_bcast_event in ops_list[idx]:
            print("Received this event from a broadcast from {0}".format(idx+1))
            return idx+1

def process_loop(event_list, process_events):
    print("Process loop: {0} : {1}".format(iproc, process_events))
    for idx, event in enumerate(process_events):
        print("Event #{0} -> {1}".format(idx, event))
        recv_op = re.search("^r([1-9].*)", event) # If the event was a receive
        send_op = re.search("^s([1-9].*)", event) # If the event was a send
        bcast_op = re.search("^b([1-9].*)", event) # If the event was a broadcast
        internal_op = re.search("^([a-zA-Z].*)", event) # If the event was internal
        if recv_op:
            event_tag = recv_op.group(1)
            print("Receive with tag:", recv_op.group(1))

            #Probe for messages
            s = MPI.Status()
            comm.Probe(status=s)
            print("tag", s.tag)
            data = comm.recv(source=MPI.ANY_SOURCE, tag=int(event_tag))
            orig_idx = determine_sender_process(event_list, event_tag)
            print("Process {0} received {1} from process {2} @ {3}".format(
                iproc, 
                str(data["data"]),
                orig_idx,
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))
            
        elif send_op:
            event_tag = send_op.group(1)
            print("Send with tag:", send_op.group(1))
            dest = determine_recv_process(event_list, event_tag)
            uuid_gen = uuid.uuid4()
            message = {
                'data': uuid_gen,
                'vc': []
            }

            print("Process {0} sending message with UUID {1} to {2} @ {3}".format(
                iproc, 
                uuid_gen,
                dest,
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))

            # Send the message/UUID and VC to the destination process
            comm.send(message, dest=dest, tag=int(event_tag))
        elif bcast_op:
            event_tag = bcast_op.group(1)
            uuid_gen = uuid.uuid4()
            message = {
                'data': uuid_gen,
                'vc': []
            }
            broadcast_message(message, event_tag)
            
        elif internal_op:
            print("Process {0} internal op {1} @ {2}".format(
                iproc, 
                internal_op.group(1),
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))
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

    """
    #Send/receive (unicast)
    event_list = [
            "s1, a, b, r2", #Process 1
            "r1, s2, r3", #Process 2
            "c, d, s3" #Process 3
    ]
    """
    #Send/receive (broadcast)
    event_list = [
            "a, b1",
            "r1, s2, b, c", 
            "r1, d, e, r2"
    ]


    if iproc == 0:
        print("Process {0} to deconstuct ops @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        sleep(2)
        for i in range(0, nproc-1):
            print("Process {0} -> {1}".format(i, event_list[i]))
            print("Process {0} sending ops to {1} @ {2} seconds".format(
                iproc, 
                i+1, #Sending to i+1
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))
            #print(ops_list[i])
            comm.send(event_list[i], dest=i+1, tag=0)
            print("\n")

        # Await until each process has finished and sent a confirmation back
            
    else:
        print("Process {0} @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        data = comm.recv(source=0, tag=0)
        process_events = data.split(", ")
        print("Process {0} obtained event_list from root @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        process_loop(event_list, process_events)
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
https://realpython.com/python-string-contains-substring/ 30th March
https://pythonprinciples.com/blog/python-convert-string-to-int/#:~:text=To%20convert%20a%20string%20to%20an%20integer%2C%20use%20the%20built,an%20integer%20as%20its%20output. 30th March
https://www.uuidgenerator.net/dev-corner/python 30th March
https://www.w3schools.com/python/python_lists_comprehension.asp 30th March
https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop 30th March
'''
