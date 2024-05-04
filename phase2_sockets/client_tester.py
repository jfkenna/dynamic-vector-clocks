from random import randint, choice
from dotenv import dotenv_values
import string
import socket
from threading import Thread
import time
import uuid
from shared.client_message import constructMessage, MessageType, messageToJson

def testThread(useSameMessageClock):
    env = dotenv_values('.env')
    processId = str(uuid.uuid4())
    print('env config:', dict(env))

    print('Begin testing...')

    clock = {processId: 1}
    while True:
        clock[processId] += 1 #placeholder, TODO replace with proper incrementing once vector clock implementation is complete
        text = ''.join([choice(string.ascii_letters) for i in range(0, randint(10000, 50000))])
        message = messageToJson(constructMessage(MessageType.BROADCAST_MESSAGE, clock, text, processId))
        print('Attempt to send message: ', message)
        targetSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        targetSocket.connect(('', int(env['PROTOCOL_PORT'])))
        sendWithHeaderAndEncoding(targetSocket, message)
        targetSocket.shutdown(1)
        targetSocket.close()

for i in range(0, 2):
    t = Thread(target=testThread, args=(False, ))
    t.start()