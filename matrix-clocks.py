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

def send_message(message, dest, tag):
    comm.send(message, dest=dest, tag=int(tag))

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
        send_message(message, idx, event_tag)

def determine_recv_process(ops_list, event_tag):
    target_event = "r" + event_tag
    print("Target event:", target_event)
    for idx in range(0, len(ops_list)):
        if target_event in ops_list[idx]:
            print("Send this event to process {0}".format(idx+1))
            return idx+1

def generate_message():
    process_id = iproc
    # Generate a random float
    r_float = random.uniform(0, 10)
    # Construct a message
    message = {
        'number': r_float,
        'vc': []
    }
    return message

def process_loop(event_list, process_events):
    # Process n's vector array
    vector_arr = numpy.zeros((nproc-1, nproc-1))
    # Process n's current main summed number 
    number_sum = 0

    print("Process loop: {0} : {1}".format(iproc, process_events))
    for idx, event in enumerate(process_events):
        print("Event #{0} -> {1}".format(idx, event))
        recv_op = re.search("^r([1-9].*)", event) # If the event was a receive
        send_op = re.search("^s([1-9].*)", event) # If the event was a send
        bcast_op = re.search("^b([1-9].*)", event) # If the event was a broadcast
        internal_op = re.search("^([a-zA-Z].*)", event) # If the event was internal
        if recv_op:
            recv_message = None
            event_tag = recv_op.group(1)
            print("Receive with tag:", recv_op.group(1))

            # Probe for messages, and obtain message from channel
            while True:
                s = MPI.Status()
                comm.Probe(tag=int(event_tag), status=s)
                # If the message in the channel matches the tag this event requires
                if str(s.tag) == event_tag:
                    # Set orig_idx (process ID) and obtain recv_message
                    orig_idx = s.tag
                    recv_message = comm.recv(source=MPI.ANY_SOURCE, tag=int(event_tag))
                    break
        
            print("Process {0} received number {1} from Process {2} @ {3}. Adding to {4}".format(
                iproc, 
                str(recv_message["number"]),
                orig_idx,
                datetime.now().strftime("%H:%M:%S.%f"), 
                str(number_sum)
            ))

            # Increment the number_sum with the received data
            number_sum += recv_message["number"]

            # Print the increment
            print("After addition, Process {0} has number sum {1}".format(
                iproc, 
                str(number_sum)
            ))
            
        elif send_op:
            event_tag = send_op.group(1)
            print("Send with tag:", send_op.group(1))
            dest = determine_recv_process(event_list, event_tag)
            message = generate_message()

            print("Process {0} sending message with generated number {1} to Process {2} @ {3}".format(
                iproc, 
                message["number"],
                dest,
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))

            # Send the message(with generated floating point number and VC) to the destination process
            send_message(message, dest, event_tag)

        elif bcast_op:
            event_tag = bcast_op.group(1)
            message = generate_message()
            broadcast_message(message, event_tag)
            
        elif internal_op:
            print("Process {0} internal event {1} @ {2}".format(
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

def event_list_from_file(file_loc):
    event_list = []
    # Open the file from args (second element)
    file = open(file_loc)
    lines = file.readlines()
    # Append each line to the events list
    for line in lines:
        event_list.append(line.strip())
    return event_list

def main():
    # Construct event list from second argument (file directory)
    file_name = sys.argv[1]
    event_list = event_list_from_file(file_name)

    if iproc == 0:
        print("Process {0} to send events to other processes @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))
        sleep(1)
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
https://ioflood.com/blog/bash-count-lines/#:~:text=To%20count%20lines%20in%20a%20file%20using%20Bash%2C%20you%20can,number%20of%20lines%20it%20contains.&text=In%20this%20example%2C%20we%20use,on%20a%20file%20named%20'filename. 30th March
https://kodekloud.com/blog/bash-getopts/ 30th March
https://linuxize.com/post/bash-functions/ 30th March
https://stackoverflow.com/questions/6348902/how-can-i-add-numbers-in-a-bash-script 30th March
https://www.geeksforgeeks.org/command-line-arguments-in-python/ 30th March
https://pynative.com/python-get-random-float-numbers/ 1st April
'''
