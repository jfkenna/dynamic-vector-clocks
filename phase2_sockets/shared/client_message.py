from enum import IntEnum
import json
import copy
import uuid

class MessageType(IntEnum):
    BROADCAST_MESSAGE = 0
    HELLO = 1
    HELLO_RESPONSE = 2
    LEAVE_NETWORK = 3

def messageToJson(message):
    return json.dumps(message)

def constructHello(sender):
    messageId = str(uuid.uuid4())
    return {
        'id': messageId,
        'sender': sender,
        'type': MessageType.HELLO
    }

def constructHelloResponse(sender, clock, undeliveredMessages):
    messageId = str(uuid.uuid4())
    return {
        'id': messageId,
        'sender': sender,
        'type': MessageType.HELLO_RESPONSE,
        'clock': clock,
        'undeliveredMessages': undeliveredMessages
    }


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
def parseJsonMessage(message, requiredFields, useClientDefaults = False):
    try:
        parsedMessage = json.loads(message)
    except:
        return None

    if useClientDefaults:
        match parsedMessage['type']:
            case MessageType.BROADCAST_MESSAGE:
                requiredFields = ['']
            case MessageType.HELLO:
                requiredFields = ['id, sender, type']
            case MessageType.HELLO_RESPONSE:
                requiredFields = ['id', 'sender', 'type', 'clock', 'undeliveredMessages']
            case MessageType.LEAVE_NETWORK:
                requiredFields = []
            case _:
                requiredFields = []
    else:
        for required in requiredFields:
            if required not in parsedMessage:
                print('Message was missing required field {0}'.format(required))
                return None

    #TODO validate type of individual fields
    return parsedMessage