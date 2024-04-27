from enum import IntEnum
import json
import copy
import uuid

#more message types to be added once we have a better idea of our system
class MessageType(IntEnum):
    BROADCAST_MESSAGE = 0
    HELLO = 1
    LEAVE_NETWORK = 2

def messageToJson(message):
    return json.dumps(message)

def constructMessage(messageType, clock, message, sender):
    messageId = str(uuid.uuid4())
    return {
        'type': messageType,
        'clock': clock or {},
        'text': message,
        'sender': sender,
        'id': messageId
    }

#return dictionary containing message values
#or None if parse failed
def parseJsonMessage(message):
    try:
        parsedMessage = json.loads(message)
    except:
        return None

    for required in ['type', 'clock', 'text', 'sender', 'id']:
        if required not in parsedMessage:
            return None

    #TODO validate type of individual fields
    return parsedMessage