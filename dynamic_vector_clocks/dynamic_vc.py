from mpi4py import MPI
import numpy as np
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

# Messaging Functions
def send_message(message, dest, tag):
    comm.send(message, dest=dest, tag=int(tag))

def broadcast_message(message, event_tag, dest_processes):
    for idx in dest_processes:
        send_message(message, idx, event_tag)

def determine_recv_process(ops_list, event_tag, event_type):
    if event_type == "send":
        target_event = "r" + event_tag
        for idx in range(0, len(ops_list)):
            if target_event in ops_list[idx]:
                return [idx+1]
    elif event_type == "broadcast":
        dest_processes = [x for x in range(1, nproc) if x != iproc]
        return dest_processes

def generate_message(destinations, process_dvc):
    message_dvc = construct_message_dvc(process_dvc)
    # Generate a random float
    r_float = generate_random_float()
    # Construct a message
    message = {
        'sender': iproc,
        'number': r_float,
        'message_dvc': message_dvc
    }

    print("Process {0} generated message heading for Process(es) {1}. Number: {2}. DVC of {3}".format(
        iproc,  
        destinations,
        r_float,
        message_dvc
    ))

    return message

def generate_random_float():
    return round(random.uniform(0, 10), 3)

# Deliverability Functions
def can_deliver_message(process_dvc, message):
    # Variable setup
    message_dvc = message["message_dvc"]                        # Message DVC
    sender_process = message["sender"]                          # Sender process number
    sender_process_index = sender_process-1                     # Sender process index

    # Check if the message's sender index in the message DVC is 1 greater than the index in the process's DVC
    sender_msg_index_valid = message_dvc[sender_process_index][1] == process_dvc[sender_process_index][1] + 1 

    # Check all other processes on the message DVC 
    other_msg_index_valid = True                                # Initially, set other_msg_index_valid True (all other known index DC)
    for x in range(nproc-1):                                    # For each known process
        if not x == sender_process_index:                       # If x is NOT the sending process of the message (other processes)
            if not message_dvc[x][1] <= process_dvc[x][1]:      # If the message index value at the other process is greater than the index in the process DVC
                other_msg_index_valid = False                   # Message needs to be enqueued
                break

    # Causal deliverability condition
    can_deliver = sender_msg_index_valid and other_msg_index_valid  
    if can_deliver: 
        print("This message satisfied the DVC causal deliverability condition. Delivering.")
    else:
        print("This message did not satisfy the DVC causal deliverability condition. Will be enqueued.")

    # Return the causal deliverability condition
    return can_deliver

def deliver_message(proces_dvc, current_number_sum, recv_message):
    new_dvc = merge_dvcs(proces_dvc, recv_message["message_dvc"])
    
    # Increment the number_sum with the received data
    new_number_sum = current_number_sum + recv_message["number"]

    # Print the increment
    print("{0} (message number) + {1} (current sum). Process {2}'s sum = {3}".format(
        str(recv_message["number"]),
        current_number_sum,
        iproc, 
        str(new_number_sum)
    ))

    return new_dvc, new_number_sum

def check_message_queue(process_dvc, number_sum, message_queue, recv_message):
    current_dvc = process_dvc
    current_number_sum = number_sum
    first_pass = True
    iterator = 0

    # Iterate over until we can't deliver any messages/nothing in the queue
    print("\nChecking messages in the message/hold back queue for deliverability")
    while True:
        if len(message_queue) >= 1:
            if iterator == len(message_queue):
                print("Exhausted all messages. Breaking")
                break
            elif message_queue[iterator] == recv_message and first_pass:
                print("This was the message that was just added - skipping it on first pass")
                iterator += 1 
            else:
                queued_message = message_queue[iterator]
                if can_deliver_message(current_dvc, queued_message):
                    current_dvc, current_number_sum = deliver_message(current_dvc, current_number_sum, queued_message)
                    message_queue.pop(iterator)
                    # Reset iterator to 0
                    iterator = 0
                    first_pass = False
                else:
                    # Move to the next iteration
                    iterator += 1
        else:
            print("No messages are in the message/hold back queue")
            break

    return current_dvc, current_number_sum

# Dynamic Vector Clock/Vector Clock Functions
def increment_dvc(dvc):
    for vc in dvc:
        if vc[0] == iproc: # Obtain this process's VC within the DVC
            vc[1] += 1 # Increment by 1
            break # Exit the loop
    return dvc

def construct_message_dvc(process_dvc):
    message_dvc = increment_dvc(process_dvc)
    # Return the incremented DVC
    return message_dvc

def merge_dvcs(message_dvc, process_dvc):
    # Create a new process DVC that will mutate on the maximum of the message/process DVCs row-wise
    new_process_dvc = process_dvc
    # For each row in the message DVC
    for row_m in message_dvc:                       # Seen message row boolean
        for row_p in new_process_dvc:               # For each row in the process DVC
            if row_m[0] == row_p[0]:                # Get each DVC's row based on the process ID
                row_p[1] = max(row_m[1], row_p[1])  # Update row_p in new_process_dvc with max(msg, p)           
    ##increment_dvc(new_process_dvc)                # Increment the process's index with the receive
    return new_process_dvc

# Process Loop / main
def process_loop(event_list, process_events):
    # Process n's initial dynamic VC
    process_dvc = []
    for i in range(1, nproc):
        process_dvc.append([i, 0])
    # Process n's current main summed number 
    number_sum = 0
    # Process n's message/hold-back queue
    message_queue = []

    for idx, event in enumerate(process_events):
        print("-----------------------\nEvent #{0} -> {1}: ({2})\n-----------------------".format(idx, event, number_sum))

        recv_op = re.search("^r([1-9].*)", event) # If the event was a receive
        send_op = re.search("^s([1-9].*)", event) # If the event was a send
        bcast_op = re.search("^b([1-9].*)", event) # If the event was a broadcast
        internal_op = re.search("^([a-zA-Z].*)", event) # If the event was internal

        if recv_op: # If the event was a receive
            recv_message = None
            event_tag = recv_op.group(1)

           # Probe for messages, and obtain message from channel should one be sent
            while True:
                s = MPI.Status()
                comm.Probe(tag=int(event_tag), status=s)
                # If the message in the channel matches the tag this event requires
                if str(s.tag) == event_tag:
                    # Set orig_idx (process ID) and obtain recv_message  
                    recv_message = comm.recv(source=MPI.ANY_SOURCE, tag=int(event_tag))
                    break
            
            print("Process {0} received number {1} from Process {2} @ {3}".format(
                iproc, 
                str(recv_message["number"]),
                str(recv_message["sender"]),
                datetime.now().strftime("%H:%M:%S.%f")
            ))

            if can_deliver_message(process_dvc, recv_message):
                process_dvc, number_sum = deliver_message(process_dvc, number_sum, recv_message)
            else:
                message_queue.append(recv_message)

            # Check if any other messages can be delivered 
            process_dvc, number_sum = check_message_queue(process_dvc, number_sum, message_queue, recv_message)
            print("DVC after {0}:\t{1}".format(event, process_dvc))
            print("Number Sum:\t", number_sum)
  
        elif send_op: # If the event was a send
            event_tag = send_op.group(1) # Obtain the send tag to add to the message
            destination_process = determine_recv_process(event_list, event_tag, "send")
            print("Unicast message to process {0}".format(destination_process))
            message = generate_message(destination_process, process_dvc)
            
            print("Process {0} sending unicast message to Process {1} @ {2}".format(
                iproc, 
                destination_process[0],
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))

             # Send the message(with generated floating point number and DVC) to the destination process
            send_message(message, destination_process[0], event_tag)

        elif bcast_op: # If the event was a broadcast
            event_tag = bcast_op.group(1)
            destination_processes = determine_recv_process(event_list, event_tag, "broadcast")
            print("Broadcast message to process(es) {0}".format(destination_processes))
            message = generate_message(destination_processes, process_dvc)

            print("Process {0} broadcasting message to Process(es) {1} @ {2}".format(
                iproc, 
                destination_processes,
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))
           
            broadcast_message(message, event_tag, destination_processes)
            
        elif internal_op: # If the event was internal
            print("Process {0} internal event {1} @ {2}".format(
                iproc, 
                internal_op.group(1),
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))

            # Increment own VC within the DVC
            process_dvc = increment_dvc(process_dvc)
            print(process_dvc)

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
        sleep(1)
        for i in range(0, nproc-1):
            comm.send(event_list[i], dest=i+1, tag=0)
    else:
        data = comm.recv(source=0, tag=0)
        process_events = data.split(", ")
        print("|----- Process {0}: {1} -----|".format(iproc, process_events))
        process_loop(event_list, process_events)
        print("")

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
https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list 1st April
https://note.nkmk.me/en/python-function-return-multiple-values/ 2nd April
https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array 2nd April
https://www.w3schools.com/python/gloss_python_array_remove.asp 2nd April
'''
