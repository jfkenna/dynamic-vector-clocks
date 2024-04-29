import socket
import uuid
import sys
from threading import Thread, Lock
from queue import Queue
from dotenv import dotenv_values
from shared.validator import validateEnv
from shared.server_message import ServerMessageType, constructBasicMessage, constructPeerResponseMessage
from shared.client_message import parseJsonMessage, messageToJson

def silentFailureClose(connection):
    try:
        connection.close()
    except:
        pass

def acceptWorker(connectionQueue, serverSocket):
    while True:
        connectionQueue.put(serverSocket.accept())

def handleMessage(message, connection, peers):
    #python switch automatically inserts break after each case
    #so control flow here is OK
    match message['type']:
        case ServerMessageType.GET_PEERS:
            with lock:
                response = messageToJson(constructPeerResponseMessage(list(peers.keys())))
            connection.send(response.encode('utf-8'))

        case ServerMessageType.REGISTER_PEER:
            peerKey = connection.getpeername()[0]
            with lock:
                peers[peerKey] = True
            response = messageToJson(constructBasicMessage(ServerMessageType.OK))
            connection.send(response.encode('utf-8'))

        case ServerMessageType.DEREGISTER_PEER:
            peerKey = connection.getpeername()[0]
            with lock:
                if peerKey in peers:
                    del peers[peerKey]
            response = messageToJson(constructBasicMessage(ServerMessageType.OK))
            connection.send(response.encode('utf-8'))

        case _:
            response = messageToJson(constructBasicMessage(ServerMessageType.BAD_MESSAGE))
            connection.send(response.encode('utf-8'))
    print('After operation {0}'.format(peers))
    return

def worker(connectionQueue, peers):
    while True:
        connection, adr = connectionQueue.get()
        #TODO properly read until seperator is reached
        #for now, just assume total message size will be < 1024
        try:
            data = connection.recv(1024)
        except socket.error:
            print('Error reading incoming message')
            silentFailureClose(connection)
            continue

        parsedMessage = parseJsonMessage(data, ['id', 'type'])
        if parsedMessage == None:
            response = messageToJson(constructBasicMessage(ServerMessageType.BAD_MESSAGE))
            silentFailureClose(connection)
            continue

        try:
            handleMessage(parsedMessage, connection, peers)
        except socket.error:
            print('Error handling message: {0}'.format(socket.error))
        
        silentFailureClose(connection)
        continue


def main():
    #shared data
    connectionQueue = Queue()
    peers = {}
    
    #initial setup copied from client
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((ip, int(env['PROTOCOL_PORT_SERVER'])))
    acceptSocket.listen()
    print('Server listening at {0} on port {1}'.format(ip, env['PROTOCOL_PORT_SERVER']))
    acceptThread = Thread(target=acceptWorker, args=(connectionQueue, acceptSocket, ))
    acceptThread.start()
    workerThread = Thread(target=worker, args=(connectionQueue, peers))
    workerThread.start()
    acceptThread.join()
    workerThread.join()


if len(sys.argv) < 2:
    print("You must provide the server ip, exiting...")
    exit()

env = dotenv_values('.env')
if validateEnv(env, ['PROTOCOL_PORT_SERVER']) == None:
    exit()
ip = sys.argv[1]
lock = Lock()
main()