from enum import IntEnum
import re 

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