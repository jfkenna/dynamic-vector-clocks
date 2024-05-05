from mpi4py import MPI
from enum import IntEnum
from datetime import datetime
from time import sleep
from shared.events import EventType, determine_and_extract_event
from shared.message import determine_recv_process, generate_random_float, send_message, broadcast_message
from shared.setup import event_list_from_file
import sys

# MPI World Setup 
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

# Messaging Functions
def generate_message(destinations, process_dvc):
    message_dvc = construct_message_dvc(process_dvc)                # Constuct the DVC for the message
    r_float = generate_random_float()                               # Generate a random floating-point number 
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
                break                                           # Break from checking other non-sender indexes

    # Causal deliverability condition
    can_deliver = sender_msg_index_valid and other_msg_index_valid  

    # Return the causal deliverability condition
    return can_deliver

def deliver_message(proces_dvc, current_number_sum, recv_message):
    # Upon message delivery - merge the message/process DVCs and calculate the new sum
    new_dvc = merge_dvcs(proces_dvc, recv_message["message_dvc"])       # Merging the DVCs to create new_dvc
    new_number_sum = current_number_sum + recv_message["number"]        # Add the floating-point numbers to create new_number_sum

    # Print the incrementation of number_sum upon message delivery
    print("{0} (message number) + {1} (current sum). Process {2}'s sum = {3}".format(
        str(recv_message["number"]), current_number_sum, iproc,  str(new_number_sum)
    ))

    # Return the new DVC and number sum for printing at event closure.
    return new_dvc, new_number_sum

def check_message_queue(process_dvc, number_sum, message_queue, recv_message):
    # Setting up variables for checking the message/hold-back queue
    current_dvc = process_dvc               # current_dvc: the process's original DVC coming into this function
    current_number_sum = number_sum         # current_number_sum: the process's original floating-point number
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
                    print("This queued message satisfied the causal deliverability condition. Will be delivered.")     # Message will be delivered
                    current_dvc, current_number_sum = deliver_message(current_dvc, current_number_sum, queued_message)      # Deliver the message and set current DVC/sum to new values
                    message_queue.pop(iterator)                                                         # Pop off the message from the queue 
                    iterator = 0                                                                        # Reset the iterator back to 0 (to check all messages again)
                    first_pass = False                                                                  # No longer the first pass
                else:                                                                                   # Otherwise, message can't be delivered
                    print("This queued message did not satisfy the causal deliverability condition. Will remain enqueued.")    # Message remains in the queue
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

        # Match the event and extract details via regex
        event_result = determine_and_extract_event(event)

        # Match based on the second element of event_result (event type)
        match event_result[1]:
            # If the event is a receive event
            case EventType.RECEIVE_EVENT:
                recv_message = None             # Set the initial recv_message to None
                event_tag = event_result[0].group(1)    # Parse the event_tag from the first group in event_result[0]

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

                # If the message can be delivered now - deliver it.
                if can_deliver_message(process_dvc, recv_message):
                    print("This message satisfied the DVC causal deliverability condition. Delivering.")
                    process_dvc, number_sum = deliver_message(process_dvc, number_sum, recv_message)
                # Otherwise push it to the message/hold-back queue
                else:
                    print("This message did not satisfy the DVC causal deliverability condition. Will be enqueued.")
                    message_queue.append(recv_message)

                # Check if any other messages can be delivered in the message/hold-back queue
                process_dvc, number_sum = check_message_queue(process_dvc, number_sum, message_queue, recv_message)

                # Print the current DVC after this event/potential deliveries and the current number sum
                print("DVC after {0}:\t{1}".format(event, process_dvc))
                print("Number Sum:\t", number_sum)

            # If the event is a broadcast event
            case EventType.BROADCAST_EVENT:
                event_tag = event_result[0].group(1)                                                                # Parse the event_tag from the first group in event_result[0]
                destination_processes = determine_recv_process(iproc, nproc, event_list, event_tag, EventType.BROADCAST_EVENT)    # Determine the receiving process(es) for this broadcast message
                print("Broadcast message to process(es) {0}".format(destination_processes))                         # Printing of upcoming broadcast message sending
                message = generate_message(destination_processes, process_dvc)                                      # Generate the message (message DVC and floating-point number)

                # Print of imminent message broadcast to the destination process(es)
                print("Process {0} broadcasting message to Process(es) {1} @ {2}".format(
                    iproc, destination_processes, datetime.now().strftime("%H:%M:%S.%f"), 
                ))
            
                # Broadcast the message(with generated floating point number and DVC) to the destination process(es)
                broadcast_message(comm, message, event_tag, destination_processes)

            # If the event is a send/unicast event
            case EventType.UNICAST_EVENT:
                event_tag = event_result[0].group(1)                                                            # Parse the event_tag from the first group in event_result[0]
                destination_process = determine_recv_process(iproc, nproc, event_list, event_tag, EventType.UNICAST_EVENT)    # Determine the receiving process for this message
                print("Unicast message to process {0}".format(destination_process))                             # Printing of upcoming message sending
                message = generate_message(destination_process, process_dvc)                                    # Generate the message (message DVC and floating-point number)
                
                # Print of imminent message sending to the destination process
                print("Process {0} sending unicast message to Process {1} @ {2}".format(
                    iproc, destination_process[0], datetime.now().strftime("%H:%M:%S.%f"), 
                ))

                # Send the message(with generated floating point number and DVC) to the destination process
                send_message(comm, message, destination_process[0], event_tag)

            # If the event is an internal process event
            case EventType.INTERNAL_EVENT:
                # Print of internal event occuring at the process
                print("Process {0} internal event {1} @ {2}".format(
                    iproc, event_result[0].group(1), datetime.now().strftime("%H:%M:%S.%f"), 
                ))

                # Generate and add a random floating-point number to this process's current stored number
                r_float = generate_random_float()       # Generate a random floating-point number    
                number_sum += r_float                   # Increment the number_sum with the received data

                # Print the increment and new number sum
                print("{0} (generated number) for internal event. Process {1}'s sum = {2}".format(
                    str(r_float), iproc,  str(number_sum)
                ))                

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
Bibliography
[1] N. Meghanathan. Module 6.2.3 Matrix Algorithm Causal Delivery of Messages. (Nov. 12, 2013). Accessed: Mar. 13, 2024. [Online video]. Available: https://www.youtube.com/watch?v=WgTx7BHWzts.
[2] T. Landes. "Dynamic Vector Clocks for Consistent Ordering of Events in Dynamic Distributed Applications." in International Conference on Parallel and Distributed Processing Techniques and Applications, Las Vegas, Nevada, USA, 2006, pp.1-7.
[3] L. Lafayette. (2021). The Spartan HPC System at the University of Melbourne [PDF]. Available: https://canvas.lms.unimelb.edu.au/courses/105440/files/7018506/download?download_frd=1.
[4] L. Dalcin. "Tutorial". MPI for Python. https://mpi4py.readthedocs.io/en/stable/tutorial.html (accessed Mar. 13, 2024).
[5] Jurudocs. "Format a datetime into a string with milliseconds". Stack Overflow. https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds (accessed Mar. 13, 2024).
[6] M. Toboggan. "How to get a random number between a float range?". Stack Overflow. https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range (accessed Mar. 15, 2024).
[7] NumPy Developers. "numpy.zeros". NumPy. https://numpy.org/doc/stable/reference/generated/numpy.zeros.html (accessed Mar. 16, 2024).
[8] New York University. "Non-blocking Communication". GitHub Pages. https://nyu-cds.github.io/python-mpi/03-nonblocking/ (accessed Mar. 24, 2024).
[9] L. Dalcin. "mpi4py.MPI.Message". MPI for Python. https://mpi4py.readthedocs.io/en/stable/reference/mpi4py.MPI.Message.html (accessed Mar. 30, 2024).
[10] W3Schools. "Python String split() Method". W3Schools. https://www.w3schools.com/python/ref_string_split.asp (accessed Mar. 30, 2024).
[11] C. Kolade. "Python Switch Statement - Switch Case Example". freeCodeCamp. https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ (accessed Mar. 30, 2024).
[12] spiderman. "How to find string that start with one letter then numbers". FME Community. https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 (accessed Mar. 30, 2024).
[13] TutorialsTeacher. "Grouping in Regex". TutorialsTeacher. https://www.tutorialsteacher.com/regex/grouping (accessed Mar. 30, 2024).
[14] hoju. "Extract part of a regex match". Stack Overflow. https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match (accessed Mar. 30, 2024).
[15] M. Breuss. "How to Check if a Python String Contains a Substring". Real Python. https://realpython.com/python-string-contains-substring/ (accessed Mar. 30, 2024).
[16] Python Principles. "How to convert a string to int in Python". Python Principles. https://pythonprinciples.com/blog/python-convert-string-to-int/ (accessed Mar. 30, 2024).
[17] TransparenTech LLC. "Generate a UUID in Python". UUID Generator. https://www.uuidgenerator.net/dev-corner/python/ (accessed Mar. 30, 2024).
[18] W3Schools. "Python - List Comprehension". W3Schools. https://www.w3schools.com/python/python_lists_comprehension.asp (accessed Mar. 30, 2024).
[19] greye. "Get loop count inside a for-loop [duplicate]". Stack Overflow. https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop (accessed Mar. 30, 2024).
[20] G. Ramuglia. "Using Bash to Count Lines in a File: A File Handling Tutorial". I/O Flood. https://ioflood.com/blog/bash-count-lines/ (accessed Mar. 30, 2024).
[21] H. Sundaray. "How to Use Bash Getopts With Examples". KodeKloud. https://kodekloud.com/blog/bash-getopts/ (accessed Mar. 30, 2024).
[22] Linuxize. "Bash Functions". Linuxize. https://linuxize.com/post/bash-functions/ (accessed Mar. 30, 2024).
[23] Nick. "How can I add numbers in a Bash script?". Stack Overflow. https://stackoverflow.com/questions/6348902/how-can-i-add-numbers-in-a-bash-script (accessed Mar. 30, 2024).
[24] GeeksForGeeks. "Command Line Arguments in Python". GeeksForGeeks. https://www.geeksforgeeks.org/command-line-arguments-in-python/ (accessed Mar. 30, 2024).
[25] V. Hule. "Generate Random Float numbers in Python using random() and Uniform()". PYnative. https://pynative.com/python-get-random-float-numbers/ (accessed Apr. 1, 2024).
[26] bhaskarc. "Iterating over a 2 dimensional python list [duplicate]". Stack Overflow. https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list (accessed Apr. 1, 2024).
[27] note.nkmk.me. "How to return multiple values from a function in Python". note.nkmk.me. https://note.nkmk.me/en/python-function-return-multiple-values/ (accessed Apr. 2, 2024).
[28] A. Luiz. "How do you extract a column from a multi-dimensional array?". Stack Overflow. https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array (accessed Apr. 2, 2024).
[29] W3Schools. "Python Remove Array Item". W3Schools. https://www.w3schools.com/python/gloss_python_array_remove.asp (accessed Apr. 2, 2024).
[30] nobody. "Python regular expressions return true/false". Stack Overflow. https://stackoverflow.com/questions/6576962/python-regular-expressions-return-true-false (accessed May. 6, 2024).
[31] A. Jalli. "Python Switch Case -- Comprehensive Guide". Medium. https://medium.com/@artturi-jalli/python-switch-case-9cd0014759e4 (accessed May. 4, 2024).
[32] Linuxize. "Bash if..else Statement". Linuxize. https://stackoverflow.com/questions/67428689/how-to-pass-multiple-flag-and-multiple-arguments-in-getopts-in-shell-script (accessed May. 4, 2024).
[33] Kivy. "Kivy: The Open Source Python App Development Framework.". Kivy. https://kivy.org/ (accessed May. 4, 2024).
[34] R. Strahl. "Getting Images into Markdown Documents and Weblog Posts with Markdown Monster". Medium. https://medium.com/markdown-monster-blog/getting-images-into-markdown-documents-and-weblog-posts-with-markdown-monster-9ec6f353d8ec (accessed May. 5, 2024).
'''