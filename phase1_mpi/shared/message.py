from .events import EventType
import random

def send_message(comm, message, dest, tag):
    comm.send(message, dest=dest, tag=int(tag))     # Send the defined message to the dest process with defined tag

def broadcast_message(comm, message, event_tag, dest_processes):
    # Send the message to all destination processes
    for idx in dest_processes:
        send_message(comm, message, idx, event_tag)       # Send the defined message to every index defined in dest_processes with the  defined tag     

def generate_random_float():
    return round(random.uniform(0, 10), 3)                      # Generation of a random floating-point number (0-10), 3 decimal places

def determine_recv_process(iproc, nproc, event_list, event_tag, event_type):
    # If the event_type is a send (unicast)
    match event_type:
        case EventType.UNICAST_EVENT:
            target_event = "r" + event_tag                              # The target_event is r<event_tag> 
            for idx in range(0, len(event_list)):                       # For the index range in event_list
                if target_event in event_list[idx]:                     # If the target_event is in the idx row of the event_list 
                    return [idx+1]                                      # Return the process ID of the row that the target_event is in
        case EventType.BROADCAST_EVENT:
            dest_processes = [x for x in range(1, nproc) if x != iproc] # Define destination processes
            return dest_processes         