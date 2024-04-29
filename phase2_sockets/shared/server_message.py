from enum import IntEnum
import uuid

class ServerMessageType(IntEnum):
    GET_PEERS = 0
    REGISTER_PEER = 1
    DEREGISTER_PEER = 2
    PEER_RESPONSE = 3
    OK = 4
    BAD_MESSAGE = 5

def constructBasicMessage(messageType):
    messageId = str(uuid.uuid4())
    return {
        'id': messageId,
        'type': messageType,
    }

def constructPeerResponseMessage(peers):
    messageId = str(uuid.uuid4())
    return {
        'id': messageId,
        'type': ServerMessageType.PEER_RESPONSE,
        'peers': peers or []
    }