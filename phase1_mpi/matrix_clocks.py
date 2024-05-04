from mpi4py import MPI
from enum import IntEnum
import numpy as np
from datetime import datetime
import random
from time import sleep
import sys
import re

# MPI World Setup
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

# Event Functions / Classes
class EventType(IntEnum):
    UNICAST_EVENT = 0
    BROADCAST_EVENT = 1
    RECEIVE_EVENT = 2
    INTERNAL_EVENT = 3

def determine_and_extract_event(event):
    # If the event is a receive event
    if re.match("^r([1-9].*)", event):      
        return re.search("^r([1-9].*)", event), EventType.RECEIVE_EVENT
    # If the event is a send/unicast event
    elif re.match("^s([1-9].*)", event):
        return re.search("^s([1-9].*)", event), EventType.UNICAST_EVENT
    # If the event is a broadcast event
    elif re.match("^b([1-9].*)", event):
        return re.search("^b([1-9].*)", event), EventType.BROADCAST_EVENT
    # If the event is an internal process event
    elif re.match("^([a-zA-Z].*)", event):
        return re.search("^([a-zA-Z].*)", event), EventType.INTERNAL_EVENT
    # Othwerwise - based on some combination not recognized - assume its an internal process event
    else: 
        return re.search("^([a-zA-Z].*)", event), EventType.INTERNAL_EVENT

# Messaging Functions
def send_message(message, dest, tag):
    comm.send(message, dest=dest, tag=int(tag))     # Send the defined message to the dest process with defined tag

def broadcast_message(message, event_tag, dest_processes):
    # Send the message to all destination processes
    for idx in dest_processes:
        send_message(message, idx, event_tag)       # Send the defined message to every index defined in dest_processes with the  defined tag

def determine_recv_process(event_list, event_tag, event_type):
    # If the event_type is a send (unicast)
    match event_type:
        case EventType.UNICAST_EVENT:
            target_event = "r" + event_tag                              # The target_event is r<event_tag> 
            for idx in range(0, len(event_list)):                       # For the index range in event_list
                if target_event in event_list[idx]:                     # If the target_event is in the idx row of the event_list 
                    return [idx+1]                                      # Return the process ID of the row that the target_event is in
        case EventType.BROADCAST_EVENT:
            dest_processes = [x for x in range(1, nproc) if x != iproc] # Define destination processes
            return dest_processes                                       # Return the destination processes
    
def generate_message(destinations, process_matrix):
    matrix_message = construct_message_matrix_clock(destinations, process_matrix)       # Constuct the matrix clock for the message
    r_float = generate_random_float()                               # Generate a random floating-point number 
    # Construct a message
    message = {
        'sender': iproc,                                            # The sender of the message
        'number': r_float,                                          # The generated floating-point number
        'matrix_message': matrix_message                            # The matrix clock affixed to the message
    }
    # Printing message generation
    print("Process {0} generated message with heading for Process(es) {1}.\nNumber: {2}.\nMC: ".format(
        iproc, destinations,r_float
    ))
    print(matrix_message)
    # Returning the message
    return message

def generate_random_float():
    return round(random.uniform(0, 10), 3)                          # Generation of a random floating-point number (0-10), 3 decimal places

# Deliverability Functions
def can_deliver_message(current_matrix, message):
    # Variable setup
    message_matrix = message["matrix_message"]                      # Message matrix clock
    recv_process_index = iproc - 1                                  # Receiver process index 
    sending_process_index = message["sender"]-1                     # Sending process index

    # Extract both the message and process matrix clock columns of the receiver process's index.
    message_matrix_column = message_matrix[:,recv_process_index]    # Message matrix clock column of receiving process
    process_matrix_column = current_matrix[:,recv_process_index]    # Current matrix clock column of receiving process
    
    # If the value of the i,j value of the row (sender)/column (receiver) is one LESS than the current process's i,j value 
    message_value_valid = message_matrix_column[sending_process_index] - 1 == process_matrix_column[sending_process_index]

    # Other columns of the process's matrix clock (not sender row) is >= the messages's values
    other_indexes_valid = True                                              # Initially, set other_indexes_valid True (all other known column values valid)
    for x in range(nproc-1):                                                # For each known process
        if not x == sending_process_index:                                  # Checking all indexes not of the sender
            if not process_matrix_column[x] >= message_matrix_column[x]:    # If the process matrix value < message value in the non-sender index
                other_indexes_valid = False                                 # Message needs to be enqueued
                break                                                       # Break from checking other non-sender indexes
                
    # Causal deliverability condition
    can_deliver = message_value_valid and other_indexes_valid

    # Printing out causal delivery conforming, or if the message will need to be enqueud
    if can_deliver: 
        print("This message satisfied the DVC causal deliverability condition. Delivering.")
    else:
        print("This message did not satisfy the DVC causal deliverability condition. Will be enqueued.")

    # Return the causal deliverability condition
    return can_deliver

def deliver_message(current_matrix, current_number_sum, recv_message):
    # Upon message delivery - merge the message/process matrix clocks and calculate the new sum
    new_matrix = maximum_matrix_values(current_matrix, recv_message["matrix_message"])      # Merging the matrix clocks to create new_matrix
    new_number_sum = current_number_sum + recv_message["number"]                            # Add the floating-point numbers to create new_number_sum 

    # Print the incrementation of number_sum upon message delivery
    print("{0} (message number) + {1} (current sum). Process {2}'s sum = {3}".format(
        str(recv_message["number"]), current_number_sum, iproc, str(new_number_sum)
    ))

    # Return the new matrix clock and number sum for printing at event closure.
    return new_matrix, new_number_sum

def check_message_queue(process_matrix, number_sum, message_queue, recv_message):
    # Setting up variables for checking the message/hold-back queue
    current_matrix = process_matrix         # current_matrix: the process's original matrix clock coming into this function
    current_number_sum = number_sum         # current_number_sum/: the process's original floating-point number
    first_pass = True                       # first_pass: whether the message queue check is in its first pass 
    iterator = 0                            # iterator: iteration integer

    # Iterate over until we can't deliver any messages/nothing in the queue
    print("\nChecking messages in the message/hold back queue for deliverability")
    while True:
        if len(message_queue) >= 1:                                 # If the length of the message_queue is >= 1, messages exist to check for delivery
            if iterator == len(message_queue):                      # If we've exhaused all messages
                print("Exhausted all messages. Breaking")           # Notifying of message exhaustion
                break                                               # Break from the while loop
            elif message_queue[iterator] == recv_message and first_pass:                    # If the message has just been added to the queue
                print("This was the message that was just added - skip it on first pass")   # Skip notification - as we've just added this to the queue.
                iterator += 1                                                               # Increment the iterator
            else:                                                                           # Otherwise - for all other messages in the queue
                queued_message = message_queue[iterator]                                    # Grab the next message in the queue      
                if can_deliver_message(current_matrix, queued_message):                     # If the message can be delivered
                    current_matrix, current_number_sum = deliver_message(current_matrix, current_number_sum, queued_message)    # Deliver the message and set current matrix clock/sum to new values
                    message_queue.pop(iterator)                                             # Pop off the message from the queue 
                    iterator = 0                                                            # Reset the iterator back to 0 (to check all messages again)
                    first_pass = False                                                      # No longer the first pass
                else:                                                                       # Otherwise, message can't be delivered
                    iterator += 1                                                           # Increment the iterator - move to the next message
        else:                                                           # Message queue is empty
            print("No messages are in the message/hold back queue")     # Notify of the empty message/hold-back queue
            break                                                       # Break from the while loop

    return current_matrix, current_number_sum                           # Return the (potentially) updated matrix clock and number sum

# Matrix Clock Functions
def maximum_matrix_values(matrix_a, matrix_b):
    max_matrix = np.zeros((nproc-1, nproc-1))                        # Create max_matrix initially of 0s
    for a in range(len(matrix_a)):                                      # For every row in matrix_a (a in range) 
        for b in range(len(matrix_b)):                                  # For every row in matrix_b (b in range)
            max_matrix[a][b] = max(matrix_a[a][b], matrix_b[a][b])      # Element max_matrix[a][b] = max value between the two matrices at that row/column
    return max_matrix                                                   # Return max_matrix

def construct_message_matrix_clock(destinations, process_matrix):
    # Extract the current matrix clock, sender row
    message_matrix_clock = process_matrix                               # Set message_matrix_clock to the current process_matrix
    sender_row = iproc - 1                                              # Obtain the sender process row
    # Increment destination columns by 1
    for dest in destinations:                                           # For each destimation
        message_matrix_clock[sender_row][dest-1] += 1                   # Increment the destination element by 1
    return message_matrix_clock                                         # Return the matrix clock to include in the message

def process_loop(event_list, process_events):
    # Process n's matrix
    process_matrix = np.zeros((nproc-1, nproc-1))
    # Process n's current main summed number 
    number_sum = 0
    # Process n's message queue
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

                # Probe for messages, and obtain message from channel
                while True:
                    s = MPI.Status()                            # Obtain the MPI Status
                    comm.Probe(tag=int(event_tag), status=s)    # Probe for messages with the deemed event_tag
                    if str(s.tag) == event_tag:                 # If a message in channel matches the event_ta
                        orig_idx = s.tag                        # Set orig_idx with the status's tag
                        recv_message = comm.recv(source=MPI.ANY_SOURCE, tag=int(event_tag))     # Receive the message
                        break                                   # Break from message probing
                
                # Print of message retrieval from the channel
                print("Process {0} received number {1} from Process {2} @ {3}".format(
                    iproc, str(recv_message["number"]), orig_idx, datetime.now().strftime("%H:%M:%S.%f")
                ))

                # If the message can be delivered now - deliver it.
                if can_deliver_message(process_matrix, recv_message):
                    process_matrix, number_sum = deliver_message(process_matrix, number_sum, recv_message)
                # Otherwise push it to the message/hold-back queue
                else:
                    message_queue.append(recv_message)

                # Check if any other messages can be delivered in the message/hold-back queue
                process_matrix, number_sum = check_message_queue(process_matrix, number_sum, message_queue, recv_message)
                
                # Print the current matrix clock after this event/potential deliveries and the current number sum
                print("MC after {0}:\n{1}".format(event, process_matrix))
                print("Number Sum:\t", number_sum)
        
            # If the event is a broadcast event
            case EventType.BROADCAST_EVENT:
                event_tag = event_result[0].group(1)                                                                # Parse the event_tag from the first group in event_result[0]
                destination_processes = determine_recv_process(event_list, event_tag, EventType.BROADCAST_EVENT)    # Determine the receiving process(es) for this broadcast message
                print("Broadcast message to Process(es) {0}".format(destination_processes))                         # Printing of upcoming broadcast message sending
                message = generate_message(destination_processes, process_matrix)                                   # Generate the message (message matrix clock and floating-point number)

                # Print of imminent message broadcast to the destination process(es)
                print("Process {0} broadcasting message to Process(es) {1} @ {2}".format(
                    iproc, destination_processes, datetime.now().strftime("%H:%M:%S.%f"), 
                ))

                # Broadcast the message(with generated floating point number and matrix clock) to the destination process(es)
                broadcast_message(message, event_tag, destination_processes)

            # If the event is a send/unicast event
            case EventType.UNICAST_EVENT:
                event_tag = event_result[0].group(1)                                                            # Parse the event_tag from the first group in event_result[0]
                destination_process = determine_recv_process(event_list, event_tag, EventType.UNICAST_EVENT)    # Determine the receiving process for this message
                print("Unicast message to process {0}".format(destination_process))                             # Printing of upcoming message sending
                message = generate_message(destination_process, process_matrix)                                 # Generate the message (message matrix-clock and floating-point number)

                # Print of imminent message sending to the destination process
                print("Process {0} sending unicast message to Process {1} @ {2}".format(
                    iproc, destination_process[0], datetime.now().strftime("%H:%M:%S.%f"), 
                ))

                # Send the message(with generated floating point number and matrix clock) to the destination process
                send_message(message, destination_process[0], event_tag)

            # If the event is an internal process event
            case EventType.INTERNAL_EVENT:
                print("Internal event at process {0} internal event {1} @ {2}".format(
                    iproc, event_result[0].group(1), datetime.now().strftime("%H:%M:%S.%f"), 
                ))

                # Generate and add a random floating-point number to this process's current stored number
                r_float = generate_random_float()       # Generate a random floating-point number    
                number_sum += r_float                   # Increment the number_sum with the received data

                # Print the increment and new number sum
                print("After addition (internal event), Process {0} has number sum {1}".format(
                    iproc, str(number_sum)
                ))

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
References
[1] Jurudocs. "Format a datetime into a string with milliseconds". Stack Overflow. https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds (accessed Mar. 13, 2024).
[2] M. Toboggan. "How to get a random number between a float range?". Stack Overflow. https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range (accessed Mar. 15, 2024).
[3] NumPy Developers. "numpy.zeros". NumPy. https://numpy.org/doc/stable/reference/generated/numpy.zeros.html (accessed Mar. 16, 2024).
[4] New York University. "Non-blocking Communication". GitHub Pages. https://nyu-cds.github.io/python-mpi/03-nonblocking/#:~:text=In%20MPI%2C%20non%2Dblocking%20communication,uniquely%20identifys%20the%20started%20operation. (accessed Mar. 24, 2024).
[5] W3Schools. "Python String split() Method". W3Schools. https://www.w3schools.com/python/ref_string_split.asp (accessed Mar. 30, 2024).
[6] C. Kolade. "Python Switch Statement – Switch Case Example". freeCodeCamp. https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ (accessed Mar. 30, 2024).
[7] spiderman. "How to find string that start with one letter then numbers". FME Community. https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 (accessed Mar. 30, 2024).
[8] TutorialsTeacher. "Grouping in Regex". TutorialsTeacher. https://www.tutorialsteacher.com/regex/grouping (accessed Mar. 30, 2024).
[9] hoju. "Extract part of a regex match". Stack Overflow. https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match (accessed Mar. 30, 2024).
[10] M. Breuss. "How to Check if a Python String Contains a Substring". Real Python. https://realpython.com/python-string-contains-substring/ (accessed Mar. 30, 2024).
[11] Python Principles. "How to convert a string to int in Python". Python Principles. https://pythonprinciples.com/blog/python-convert-string-to-int/#:~:text=To%20convert%20a%20string%20to%20an%20integer%2C%20use%20the%20built,an%20integer%20as%20its%20output. (accessed Mar. 30, 2024).
[12] TransparenTech LLC. "Generate a UUID in Python". UUID Generator. https://www.uuidgenerator.net/dev-corner/python (accessed Mar. 30, 2024).
[13] W3Schools. "Python - List Comprehension". W3Schools. https://www.w3schools.com/python/python_lists_comprehension.asp (accessed Mar. 30, 2024).
[14] greye. "Get loop count inside a for-loop [duplicate]". Stack Overflow. https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop (accessed Mar. 30, 2024).
[15] G. Ramuglia. "Using Bash to Count Lines in a File: A File Handling Tutorial". I/O Flood. https://ioflood.com/blog/bash-count-lines/#:~:text=To%20count%20lines%20in%20a%20file%20using%20Bash%2C%20you%20can,number%20of%20lines%20it%20contains.&text=In%20this%20example%2C%20we%20use,on%20a%20file%20named%20'filename. (accessed Mar. 30, 2024).
[16] H. Sundaray. "How to Use Bash Getopts With Examples". KodeKloud. https://kodekloud.com/blog/bash-getopts/ (accessed Mar. 30, 2024).
[17] Linuxize. "Bash Functions". Linuxize. https://linuxize.com/post/bash-functions/ (accessed Mar. 30, 2024).
[18] Nick. "How can I add numbers in a Bash script?". Stack Overflow. https://stackoverflow.com/questions/6348902/how-can-i-add-numbers-in-a-bash-script (accessed Mar. 30, 2024).
[19] GeeksForGeeks. "Command Line Arguments in Python". GeeksForGeeks. https://www.geeksforgeeks.org/command-line-arguments-in-python/ (accessed Mar. 30, 2024).
[20] V. Hule. "Generate Random Float numbers in Python using random() and Uniform()". PYnative. https://pynative.com/python-get-random-float-numbers/ (accessed Apr. 1, 2024).
[21] bhaskarc. "Iterating over a 2 dimensional python list [duplicate]". Stack Overflow. https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list (accessed Apr. 1, 2024).
[22] note.nkmk.me. "How to return multiple values from a function in Python". note.nkmk.me. https://note.nkmk.me/en/python-function-return-multiple-values/ (accessed Apr. 2, 2024).
[23] A. Luiz. "How do you extract a column from a multi-dimensional array?". Stack Overflow. https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array (accessed Apr. 2, 2024).
[24] W3Schools. "Python Remove Array Item". W3Schools. https://www.w3schools.com/python/gloss_python_array_remove.asp (accessed Apr. 2, 2024).
[25] nobody. "Python regular expressions return true/false". https://stackoverflow.com/questions/6576962/python-regular-expressions-return-true-false (accessed May. 6, 2024).
[26] A. Jalli. "Python Switch Case -- Comprehensive Guide". https://medium.com/@artturi-jalli/python-switch-case-9cd0014759e4 (accessed May. 4, 2024).
'''
