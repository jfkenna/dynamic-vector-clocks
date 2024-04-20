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

def send_message(message, dest, tag):
    comm.send(message, dest=dest, tag=int(tag))

def broadcast_message(message, event_tag, dest_processes):
    # Extract target processes (without root)
    print("Process {0} broadcasting message to {1} @ {2} ".format(
        iproc, 
        dest_processes,
        datetime.now().strftime("%H:%M:%S.%f"), 
    ))
    # Develop the matrix clock here, knowing target proce
    for idx in dest_processes:
        send_message(message, idx, event_tag)

def determine_recv_process(ops_list, event_tag, event_type):
    if event_type == "send":
        target_event = "r" + event_tag
        print("Looking for target receive event:", target_event)
        for idx in range(0, len(ops_list)):
            if target_event in ops_list[idx]:
                return [idx+1]
    elif event_type == "broadcast":
        dest_processes = [x for x in range(1, nproc) if x != iproc]
        return dest_processes

def maximum_matrix_values(matrix_a, matrix_b):
    max_matrix = numpy.zeros((nproc-1, nproc-1))
    for a in range(len(matrix_a)):
        for b in range(len(matrix_b)):
            max_matrix[a][b] = max(matrix_a[a][b], matrix_b[a][b])
    return max_matrix

def increment_dvc(dvc):
    for vc in dvc:
        if vc[0] == iproc: # Obtain this process's VC within the DVC
            vc[1] += 1 # Increment by 1
            break # Exit the loop
    return dvc

def construct_message_dvc(destinations, process_dvc):
    print("Generating DVC to include in message. From process {0} to {1}".format(
        iproc,
        destinations
    ))

    message_dvc = increment_dvc(process_dvc)
    # Return the incremented DVC
    return message_dvc

def merge_dvcs(message_dvc, message_iproc, process_dvc):
    # Add the DVC to the process's DVC (if not existing), else 
    print("---proc---")
    print(process_dvc)
    print("From process {0}".format(message_iproc))
    print("---msg---")
    print(message_dvc)
    new_process_dvc = process_dvc
    # Check if the receiver has a VC for the sending process
    recv_iproc_before = False
    print("checking rows")
    for row in process_dvc:
        if row[0] == message_iproc:
            recv_iproc_before = True
            break
    if not recv_iproc_before:
        print("{0} hasnt heard from {1} before".format(
            iproc,
            message_iproc
        ))
        # Extract message_iproc's row
        message_iproc_vc = None
        for row in message_dvc:
            if row[0] == message_iproc:
                message_iproc_vc = row
                break
        # Add this new row to process_dvc
        new_process_dvc.append(message_iproc_vc)
        increment_dvc(new_process_dvc)
        print(new_process_dvc)
    return new_process_dvc

def generate_message(destinations, process_dvc):
    print("Process {0} generating message/updated DVC to destinations {1}. Initial DVC of".format(
        iproc,  
        destinations
    ))
    print(process_dvc)
    message_dvc = construct_message_dvc(destinations, process_dvc)
    # Generate a random float
    r_float = generate_random_float()
    # Construct a message
    message = {
        'sender': iproc,
        'number': r_float,
        'message_dvc': message_dvc
    }
    print("Process {0} generated DVC and message heading for Process {1}. Generated DVC of:".format(
        iproc,  
        destinations
    ))
    print(message_dvc)
    return message

def generate_random_float():
    return random.uniform(0, 10)

def deliver_message(current_matrix, current_number_sum, recv_message):
    new_matrix = maximum_matrix_values(current_matrix, recv_message["matrix_message"])
    
    # Increment the number_sum with the received data
    new_number_sum = current_number_sum + recv_message["number"]

    # Print the increment
    print("After addition, Process {0} has number sum {1}".format(
        iproc, 
        str(new_number_sum)
    ))

    return new_matrix, new_number_sum

def can_deliver_message(current_matrix, message):
    message_matrix = message["matrix_message"]
    recv_process_index = iproc - 1
    sending_process_index = message["sender"]-1
    print("The received matrix clock of Process {0} (index {1}) with the message from Process {2} (index {3})".format(
        iproc,
        recv_process_index,
        message["sender"],
        sending_process_index
    ))

    message_matrix_column = message_matrix[:,recv_process_index]
    process_matrix_column = current_matrix[:,recv_process_index]
    
    # If the value of the i,j value of the row (sender)/column (receiver) is one LESS than the current process's i,j value 
    message_value_valid = message_matrix_column[sending_process_index] - 1 == process_matrix_column[sending_process_index]
    # Other columns of the process's matrix clock (not sender row) is >= the messages's values
    other_indexes_valid = True
    for x in range(nproc-1):
        if not x == sending_process_index: # Checking all indexes not of the sender
            if not process_matrix_column[x] >= message_matrix_column[x]: # Ensure process matrix value >= message value in non-sender values
                print("This is invalid - we need to queue this message!")
                other_indexes_valid = False
                break

    can_deliver = message_value_valid and other_indexes_valid
    return can_deliver

def check_message_queue(process_matrix, number_sum, message_queue, recv_message):
    current_matrix = process_matrix
    current_number_sum = number_sum
    first_pass = True

    print("The current message queue")
    print(message_queue)

    iterating = True
    iterator = 0

    while iterating:
        if len(message_queue) >= 1:
            print("Need to check if we can deliver messages")
            if iterator == len(message_queue):
                print("Exhausted all messages. Breaking")
                break
            elif message_queue[iterator] == recv_message and first_pass:
                print("This was the message that was just added - skip it only on the first pass")
                iterator += 1 
            else:
                queued_message = message_queue[iterator]
                print("Grabbing index {0} of the message queue")
                print(message_queue[iterator])
                if can_deliver_message(current_matrix, queued_message):
                    current_matrix, current_number_sum = deliver_message(process_matrix, current_number_sum, queued_message)
                    message_queue.pop(iterator)
                    # Reset iterator to 0
                    iterator = 0
                    first_pass = False
                else:
                    # Move to the next iteration
                    iterator += 1
        else:
            print("No messages in the queue")
            break

    return current_matrix, current_number_sum

def process_loop(event_list, process_events):
    # Process n's initial dynamic VC
    process_dvc = [[iproc, 0]]
    # Process n's current main summed number 
    number_sum = 0
    # Process n's message queue
    message_queue = []

    print("Process loop: {0} : {1}".format(iproc, process_events))
    print(process_dvc)     

    for idx, event in enumerate(process_events):
        print("----------")
        
        print("Event #{0} -> {1}".format(idx, event))
        recv_op = re.search("^r([1-9].*)", event) # If the event was a receive
        send_op = re.search("^s([1-9].*)", event) # If the event was a send
        bcast_op = re.search("^b([1-9].*)", event) # If the event was a broadcast
        internal_op = re.search("^([a-zA-Z].*)", event) # If the event was internal

        if recv_op: # If the event was a receive
            print("Receive event")
            recv_message = None
            event_tag = recv_op.group(1)
            print("Receive with tag:", event_tag)

           # Probe for messages, and obtain message from channel should one be sent
            while True:
                s = MPI.Status()
                comm.Probe(tag=int(event_tag), status=s)
                # If the message in the channel matches the tag this event requires
                if str(s.tag) == event_tag:
                    # Set orig_idx (process ID) and obtain recv_message
                    orig_idx = s.tag
                    recv_message = comm.recv(source=MPI.ANY_SOURCE, tag=int(event_tag))
                    print("got")
                    break
            
            print("Process {0} received number {1} from Process {2} @ {3}. Adding to {4}. DVC is".format(
                iproc, 
                str(recv_message["number"]),
                str(recv_message["sender"]),
                datetime.now().strftime("%H:%M:%S.%f"), 
                str(number_sum)
            ))
            message_dvc = recv_message["message_dvc"]
            message_iproc = recv_message["sender"]
            process_dvc = merge_dvcs(message_dvc, message_iproc, process_dvc)
         
        elif send_op: # If the event was a send
            print("Send event")
            event_tag = send_op.group(1) # Obtain the send tag to add to the message
            print("Send with tag:", event_tag)
            destination_process = determine_recv_process(event_list, event_tag, "send")
            print("Send this event to process {0}".format(destination_process))
            message = generate_message(destination_process, process_dvc)
            
            print("Process {0} sending message with generated number {1} to Process {2} @ {3}".format(
                iproc, 
                message["number"],
                destination_process[0],
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))

             # Send the message(with generated floating point number and DVC) to the destination process
            send_message(message, destination_process[0], event_tag)

        elif bcast_op: # If the event was a broadcast
            print("Broadcast event")
            
        elif internal_op: # If the event was internal
            print("Process {0} internal event {1} @ {2}".format(
                iproc, 
                internal_op.group(1),
                datetime.now().strftime("%H:%M:%S.%f"), 
            ))

            # Increment own VC within the DVC
            process_dvc = increment_dvc(process_dvc)
            print(process_dvc)

        print("----------")

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
https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list 1st April
https://note.nkmk.me/en/python-function-return-multiple-values/ 2nd April
https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array 2nd April
https://www.w3schools.com/python/gloss_python_array_remove.asp 2nd April
'''
