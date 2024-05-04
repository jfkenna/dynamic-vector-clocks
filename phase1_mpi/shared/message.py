from .events import EventType

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