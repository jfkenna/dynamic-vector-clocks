from enum import IntEnum
import json
import copy
import uuid

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
def parseJsonMessage(message, requiredFields):
    try:
        parsedMessage = json.loads(message)
    except:
        return None

    for required in requiredFields:
        if required not in parsedMessage:
            return None

    #TODO validate type of individual fields
    return parsedMessage