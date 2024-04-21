from enum import IntEnum
import json

#more message types to be added once we have a better idea of our system
class MessageType(IntEnum):
    DIRECT_MESSAGE = 0
    BROADCAST_MESSAGE = 1
    LEAVE_NETWORK = 2

def constructJsonMessage(messageType, clock, message):
    return json.dumps({
        'type': messageType,
        'clock': clock or {},
        'text': message
    })

#return dictionary containing message values
#or None if parse failed
def parseJsonMessage(message):
    try:
        parsedMessage = json.loads(message)
    except:
        return None

    for required in ['type', 'clock', 'text']:
        if required not in parsedMessage:
            return None

    #TODO validate type of individual fields
    return parsedMessage