from random import randint, choice
from dotenv import dotenv_values
import string
import socket
from threading import Thread
import time
from shared.message import constructJsonMessage, MessageType

def testThread():
    env = dotenv_values('.env')
    print('env config:', dict(env))

    print('Begin testing...')

    while True:
        text = ''.join([choice(string.ascii_letters) for i in range(0, randint(5, 50))])
        message = constructJsonMessage(MessageType.DIRECT_MESSAGE, {'test': 1000}, text)
        print('Attempt to send message: ', message)
        targetSocket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        targetSocket.connect((env['CLIENT_LISTEN_IP'], int(env['CLIENT_LISTEN_PORT'])))
        targetSocket.send(message.encode('utf-8'))
        targetSocket.shutdown(1)
        targetSocket.close()

for i in range(0, 100):
    t = Thread(target=testThread)
    t.start()