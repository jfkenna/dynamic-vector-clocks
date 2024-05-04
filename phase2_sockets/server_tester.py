from random import randint, choice
import sys
from dotenv import dotenv_values
import string
import socket
from threading import Thread
import time
import uuid
from shared.client_message import messageToJson, parseJsonMessage
from shared.server_message import ServerMessageType, constructBasicMessage

def buildRandomMessage():
    match randint(0, 3):
        case 0:
            return constructBasicMessage(ServerMessageType.GET_PEERS)
        case 1:
            return constructBasicMessage(ServerMessageType.REGISTER_PEER)
        case 2:
            return constructBasicMessage(ServerMessageType.DEREGISTER_PEER)
        case 3:
            return constructBasicMessage(ServerMessageType.OK) #unexpected message type, server should reply with OK

def testThread(useSameMessageClock):
    env = dotenv_values('.env')
    print('env config:', dict(env))
    print('Begin testing...')

    while True:
        message = messageToJson(buildRandomMessage())
        print('Attempt to send message: ', message)
        targetSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        targetSocket.connect((ip, int(env['PROTOCOL_PORT_SERVER'])))
        sendWithHeaderAndEncoding(targetSocket, message)
        readMessage = targetSocket.recv(1024)
        print(parseJsonMessage(readMessage, ['type', 'id']))
        targetSocket.shutdown(1)
        targetSocket.close()

if len(sys.argv) < 2:
    print("You must provide the server ip, exiting...")
    exit()

ip = sys.argv[1]
for i in range(0, 1):
    t = Thread(target=testThread, args=(False, ))
    t.start()