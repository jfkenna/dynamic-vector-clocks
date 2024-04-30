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
    comm.send(message, dest=dest, tag=int(tag))     # Send the defined message to the dest process with defined tag

def broadcast_message(message, event_tag, dest_processes):
    # Send the message to all destination processes
    for idx in dest_processes:
        send_message(message, idx, event_tag)       # Send the defined message to every index defined in dest_processes with the  defined tag

def determine_recv_process(event_list, event_tag, event_type):
    # If the event_type is a send (unicast)
    if event_type == "send":
        target_event = "r" + event_tag                              # The target_event is r<event_tag> 
        for idx in range(0, len(event_list)):                       # For the index range in event_list
            if target_event in event_list[idx]:                     # If the target_event is in the idx row of the event_list 
                return [idx+1]                                      # Return the process ID of the row that the target_event is in
    # If the event_ty[e is a broadcast
    elif event_type == "broadcast":
        dest_processes = [x for x in range(1, nproc) if x != iproc] # Define destination processes
        return dest_processes                                       # Return the destination processes

def generate_message(destinations, process_dvc):
    message_dvc = construct_message_dvc(process_dvc)                # Constuct the DVC for the message
    r_float = generate_random_float()                               # Generate a random floating point number 
    # Construct a message
    message = {
        'sender': iproc,                                            # The sender of the message
        'number': r_float,                                          # The generated floating-point number
        'message_dvc': message_dvc                                  # The DVC affixed to the message
    }
    # Printing message generation
    print("Process {0} generated message heading for Process(es) {1}. Number: {2}. DVC of {3}".format(
        iproc, destinations, r_float, message_dvc
    ))
    # Returning the message
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

    # Printing out causal delivery conforming, or if the message will need to be enqueud
    if can_deliver: 
        print("This message satisfied the DVC causal deliverability condition. Delivering.")
    else:
        print("This message did not satisfy the DVC causal deliverability condition. Will be enqueued.")

    # Return the causal deliverability condition
    return can_deliver

def deliver_message(proces_dvc, current_number_sum, recv_message):
    # Upon message delivery - merge the message/process DVCs and increment the sum
    new_dvc = merge_dvcs(proces_dvc, recv_message["message_dvc"])       # Merging the DVCs and create new_dvc
    new_number_sum = current_number_sum + recv_message["number"]        # Add the floating-point numbers and create new_number_sum

    # Print the incrementation of number_sum upon message delivery
    print("{0} (message number) + {1} (current sum). Process {2}'s sum = {3}".format(
        str(recv_message["number"]), current_number_sum, iproc,  str(new_number_sum)
    ))

    # Return the new DVC and number sum for printing at event closure.
    return new_dvc, new_number_sum

def check_message_queue(process_dvc, number_sum, message_queue, recv_message):
    # Setting up variables for checking the message/hold-back queue
    current_dvc = process_dvc               # current_dvc: the processe's original DVC coming into this function
    current_number_sum = number_sum         # current_number_sum/: the process's original floating-point number
    first_pass = True                       # first_pass: whether the message queue check is in its first pass 
    iterator = 0                            # iterator: iteration integer

    # Iterate over until we can't deliver any messages/nothing in the queue
    print("\nChecking messages in the message/hold back queue for deliverability")
    while True:
        if len(message_queue) >= 1:                             # If the length of the message_queue is >= 1, messages exist to check for delivery
            if iterator == len(message_queue):                  # If we've exhaused all messages
                print("Exhausted all messages. Breaking")       # Notifying of message exhaustion
                break                                           # Break from the while loop
            elif message_queue[iterator] == recv_message and first_pass:                                # If the message has just been added to the queue
                print("This was the message that was just added - skipping it on first pass")           # Skip notification - as we've just added this to the queue.
                iterator += 1                                                                           # Increment the iterator
            else:                                                                                       # Otherwise - for all other messages in the queue
                queued_message = message_queue[iterator]                                                # Grab the next message in the queue                                     
                if can_deliver_message(current_dvc, queued_message):                                    # If the message can be delivered
                    current_dvc, current_number_sum = deliver_message(current_dvc, current_number_sum, queued_message)      # Deliver the message and set current DVC/sum to new values
                    message_queue.pop(iterator)                                                         # Pop off the message from the queue 
                    iterator = 0                                                                        # Reset the iterator back to 0 (to check all messages again)
                    first_pass = False                                                                  # No longer the first pass
                else:                                                                                   # Otherwise, message can't be delivered
                    iterator += 1                                                                       # Increment the iterator - move to the next message
        else:                                                                       # Message queue is empty
            print("No messages are in the message/hold back queue")                 # Notify of the empty message/hold-back queue
            break                                                                   # Break from the while loop

    return current_dvc, current_number_sum                                          # Return the (potentially) updated DVC and number sum

# Dynamic Vector Clock/Vector Clock Functions
def increment_dvc(dvc):
    for vc in dvc:                      # For each induvidual VC within the DVC
        if vc[0] == iproc:              # Obtain this process's VC within the DVC
            vc[1] += 1                  # Increment the processes' clock count by 1
            break                       # Exit the loop
    return dvc

def construct_message_dvc(process_dvc):
    message_dvc = increment_dvc(process_dvc)        # Increment the DVC for a new message
    return message_dvc                              # Return the message DVC

def merge_dvcs(message_dvc, process_dvc):
    # Create a new process DVC that will mutate on the maximum of the message/process DVCs row-wise
    new_process_dvc = process_dvc                   # Create a new_process_dvc based off the current process DVC
    for row_m in message_dvc:                       # For each row in the message DVC
        for row_p in new_process_dvc:               # For each row in the process DVC
            if row_m[0] == row_p[0]:                # Get each DVC's row based on the process ID
                row_p[1] = max(row_m[1], row_p[1])  # Update row_p in new_process_dvc with max(message row, process row)           
    return new_process_dvc                          # Return new_process_dvc 

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

        recv_op = re.search("^r([1-9].*)", event)               # If the event was a receive
        send_op = re.search("^s([1-9].*)", event)               # If the event was a send
        bcast_op = re.search("^b([1-9].*)", event)              # If the event was a broadcast
        internal_op = re.search("^([a-zA-Z].*)", event)         # If the event was internal

        if recv_op:                         # If the event was a receive
            recv_message = None             # Set the initial recv_message to None
            event_tag = recv_op.group(1)    # Parse the event_tag from the first group in recv_op

           # Probe for messages, and obtain message from channel should one be sent
            while True:
                s = MPI.Status()                            # Obtain the MPI Status
                comm.Probe(tag=int(event_tag), status=s)    # Probe for messages with the deemed event_tag
                if str(s.tag) == event_tag:                 # If a message in channel matches the event_tag
                    recv_message = comm.recv(source=MPI.ANY_SOURCE, tag=int(event_tag))     # Receive the message
                    break                                   # Break from message probing
            
            # Print of message retrieval from the channel
            print("Process {0} received number {1} from Process {2} @ {3}".format(
                iproc, str(recv_message["number"]), str(recv_message["sender"]), datetime.now().strftime("%H:%M:%S.%f")
            ))

            # If te message can be delivered now - deliver it.
            if can_deliver_message(process_dvc, recv_message):
                process_dvc, number_sum = deliver_message(process_dvc, number_sum, recv_message)
            # Otherwise push it to the message/hold-back queue
            else:
                message_queue.append(recv_message)

            # Check if any other messages can be delivered in the message/hold-back queue
            process_dvc, number_sum = check_message_queue(process_dvc, number_sum, message_queue, recv_message)

            # Print the current DVC after this event and the current number sum
            print("DVC after {0}:\t{1}".format(event, process_dvc))
            print("Number Sum:\t", number_sum)
  
        elif send_op:                                                                       # If the event was a send
            event_tag = send_op.group(1)                                                    # Parse the event_tag from the first group in send_op
            destination_process = determine_recv_process(event_list, event_tag, "send")     # Determine the receiving process for this message
            print("Unicast message to process {0}".format(destination_process))             # Printing of upcoming message sending
            message = generate_message(destination_process, process_dvc)                    # Generate the message (message DVC and floating-point number)
            
            # Print of imminent message sending to the destination process
            print("Process {0} sending unicast message to Process {1} @ {2}".format(
                iproc, destination_process[0], datetime.now().strftime("%H:%M:%S.%f"), 
            ))

             # Send the message(with generated floating point number and DVC) to the destination process
            send_message(message, destination_process[0], event_tag)

        elif bcast_op:                                                                          # If the event was a broadcast
            event_tag = bcast_op.group(1)                                                       # Parse the event_tag from the first group in bcast_op
            destination_processes = determine_recv_process(event_list, event_tag, "broadcast")  # Determine the receiving process(es) for this broadcast message
            print("Broadcast message to process(es) {0}".format(destination_processes))         # Printing of upcoming broadcast message sending
            message = generate_message(destination_processes, process_dvc)                      # Generate the message (message DVC and floating-point number)

            # Print of imminent message broadcast to the destination process(es)
            print("Process {0} broadcasting message to Process(es) {1} @ {2}".format(
                iproc, destination_processes, datetime.now().strftime("%H:%M:%S.%f"), 
            ))
           
            # Broadcast the message(with generated floating point number and DVC) to the destination process(es)
            broadcast_message(message, event_tag, destination_processes)
            
        elif internal_op:           # If the event was internal
            # Print of internal event occuring at the process
            print("Process {0} internal event {1} @ {2}".format(
                iproc, internal_op.group(1), datetime.now().strftime("%H:%M:%S.%f"), 
            ))

            process_dvc = increment_dvc(process_dvc)    # Increment the DVC (process's internal event) 
            print(process_dvc)                          # Print out the current Process's DVC

def event_list_from_file(file_loc):
    event_list = []                         # Construct an event_list array
    file = open(file_loc)                   # Open the file determined by sys.argv[1]
    lines = file.readlines()                # Read the lines of the file
    for line in lines:                      # For each line that has been read
        event_list.append(line.strip())     # Append the line to the event_list
    return event_list                       # Return event_list

def main():
    # Construct event list from second argument (file directory)
    file_name = sys.argv[1]                         # Obtain the file_name from sys.argv[1]
    event_list = event_list_from_file(file_name)    # Create the event_list

    # Process 0 to coordinate sending of events for each process
    if iproc == 0:                                          # If process 0
        sleep(1)                                            # Sleep for a second to induce some delay
        for i in range(0, nproc-1):                         # For all other processes in the system
            comm.send(event_list[i], dest=i+1, tag=0)       # Send the corresponding event_list line to that process (row 1, process 1 etc)
    else:                                                   # If process N (such that N != 0 and N >=1)
        data = comm.recv(source=0, tag=0)                   # Receive data from process 0
        process_events = data.split(", ")                   # Split the events obtained by comma
        print("|----- Process {0}: {1} -----|".format(iproc, process_events))   # Print the induvidual process's events received after splitting
        process_loop(event_list, process_events)            # Invoke the main process_loop
        print("")                                           # Formatting

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
