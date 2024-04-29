import socket
import uuid
import sys
from threading import Thread, Lock
from queue import Queue
from dotenv import dotenv_values
from shared.server_message import ServerMessageType, constructBasicMessage, constructPeerResponseMessage
from shared.client_message import parseJsonMessage

def acceptWorker(connectionQueue, serverSocket):
    while True:
        connectionQueue.put(serverSocket.accept())

def handleMessage(message, connection, peers):
    #python switch automatically inserts break after each case
    #so control flow here is OK
    match messageType:
        case ServerMessageType.GET_PEERS:
            with lock:
                response = messageToJson(constructPeerResponseMessage(list(peers.keys())))
            connection.send(jsonMessage.encode('utf-8'))

        case ServerMessageType.REGISTER_PEER:
            peerKey = connection.getpeername()
            with lock:
                peers[peerKey] = True
            response = messageToJson(constructBasicMessage(ServerMessageType.OK))
            connection.send(response.encode('utf-8'))

        case ServerMessageType.DEREGISTER_PEER:
            peerKey = connection.getpeername()
            with lock:
                peers.pop(peerKey, None)
            response = messageToJson(constructBasicMessage(ServerMessageType.OK))
            connection.send(response.encode('utf-8'))

        case _:
            response = messageToJson(constructBasicMessage(ServerMessageType.BAD_MESSAGE))
            connection.send(response.encode('utf-8'))
        
    #only for test purposes
    print(peers)
    return

def worker(connectionQueue, peers):
    while True:
        message = connectionQueue.get()
        parsedMessage = parseJsonMessage(message, ['id', 'type'])
        if parsedMessage == None:
            response = messageToJson(constructBasicMessage(ServerMessageType.BAD_MESSAGE))
            connection.close()
            continue
        handleMessage(parsedMessage, connection)
        connection.close()


def main():
    #shared data
    connectionQueue = Queue()
    peers = {}
    
    #initial setup copied from client
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((ip, int(env['PROTOCOL_PORT'])))
    acceptSocket.listen()
    print('Server listening at {0} on port {1}'.format(ip, env['PROTOCOL_PORT']))
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
ip = sys.argv[1]
lock = Lock()
main()