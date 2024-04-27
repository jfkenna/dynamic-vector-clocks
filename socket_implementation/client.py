from threading import Thread
from queue import Queue
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor
from shared.message import constructMessage, parseJsonMessage, messageToJson, MessageType
import socket
import uuid
import sys

def acceptWorker(connectionQueue, serverSocket):
    print('[a0] Started')
    while True:
        connectionQueue.put(serverSocket.accept())
        #print('[a0] Accepted connection')


def sendWorker(outgoingMessageQueue, peers, processId):
    print('[s0] Started')
    while True:
        outgoingMessageText = outgoingMessageQueue.get()
        clock = {processId: str(uuid.uuid4())} #TODO replace this clock dict with the current vector clock of the process
        outgoingMessage = constructMessage(MessageType.BROADCAST_MESSAGE, clock, outgoingMessageText, processId)
        broadcastToPeers(outgoingMessage, peers)


def networkWorker(connectionQueue, receivedMessages, peers, id):
    print('[w{0}] Started'.format(id))
    while True:
        connection, adr = connectionQueue.get()
        #TODO properly read multiple datagrams until seperator is reached
        #for now, just assume total message size will be < 1024
        data = connection.recv(1024)
        message = parseJsonMessage(data)
        #print('[w{0}] Recieved message {1}'.format(id, message))
        if message == None:
            print('[w{0}] Parse error'.format(id))
            continue
        handleMessage(message, receivedMessages, peers)


def UIWorker(outgoingMessageQueue):
    print('[UI0] Started')
    while True:
        newMessageText = input()
        outgoingMessageQueue.put(newMessageText)


def handleMessage(message, receivedMessages, peers):
    if message['id'] in receivedMessages:
        return
    #add to list of received messages
    receivedMessages[message['id']] = True

    #broadcast to other peers (reliable broadcast, so each receipt will broadcast to all other known nodes)
    broadcastToPeers(message, peers)

    #TODO processing / handling / message queue / causal delivery
    #TODO
    #TODO
    #for now, just display received messages
    senderName = 'You' if (message['sender'] == processId) else message['sender'] 
    print('[{0}]: {1}'.format(senderName, message['text']))


def broadcastToPeers(message, peers):
    jsonMessage = messageToJson(message)
    for peer in peers:
        #print("trying with peer {0}".format(peer))
        #TODO add handling for errors, unresponsive peer etc.
        #TODO check this send logic is OK
        targetSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        targetSocket.connect((peer, int(env['PROTOCOL_PORT'])))
        targetSocket.send(jsonMessage.encode('utf-8'))
        targetSocket.shutdown(1)
        targetSocket.close()
        #print('broadcast {0} to {1}'.format(jsonMessage, peer))


def validateEnv(env):
    for required in ['PROTOCOL_PORT', 'CLIENT_WORKER_THREADS']:
        if required not in env:
            print(required + ' not specified')
            return False

    if not 1 <= int(env['PROTOCOL_PORT']) <= 65353:
        print("PROTOCOL_PORT is defined as {0}. Needs to be inbetween 1-65353.".format(env['PROTOCOL_PORT']))
        return False
    
    return True

def getPeerHosts():
    initialPeers = []
    print("Enter peer IPs/hostnames [enter \'finished\' to continue]")
    while True:
        peer = input('Enter hostname: ')
        if peer == 'finished' or peer == 'f':
            if (len(initialPeers) == 0):
                print('You must provide at least one peer to continue')
                continue
            return initialPeers
        try:
            resolvedAdr = socket.gethostbyname(peer)
            initialPeers.append(resolvedAdr)
            print('Added peer at {0}'.format(resolvedAdr))
        except:
            print('Couldn\'t resolve hostname, enter a different value')
            continue


def main():
    #create shared resources
    #suprisingly, default python queue is thread-safe and blocks on .get()
    connectionQueue = Queue()
    outgoingMessageQueue = Queue()
    receivedMessages = {} #TODO check if map is thread safe

    #TODO consider adding new peers at runtime based on received messages, so network is more fault tolerant
    #this is an extension, so for our first implementation just start with a fixed set of peers that we can multicast to
    peers = getPeerHosts()
    
    #setup listener
    #for now, only use ipv4 - can swap to V6 fairly easily later if we want to
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((env['CLIENT_LISTEN_IP'], int(env['PROTOCOL_PORT'])))
    acceptSocket.listen()
    print('Client listening at {0} on port {1}'.format(env['CLIENT_LISTEN_IP'], env['PROTOCOL_PORT']))
    acceptThread = Thread(target=acceptWorker, args=(connectionQueue, acceptSocket, ))
    acceptThread.start()

    #message handler threads
    handlerThreads = []
    for i in range(0, int(env['CLIENT_WORKER_THREADS'])):
        worker = Thread(target=networkWorker, args=(connectionQueue, receivedMessages, peers, i, ))
        handlerThreads.append(worker)
        worker.start()

    #thread for self-initiated messages
    sendThread = Thread(target=sendWorker, args=(outgoingMessageQueue, peers, processId))
    sendThread.start()

    #UI input thread
    inputThread = Thread(target=UIWorker, args=(outgoingMessageQueue, ))
    inputThread.start()

    inputThread.join()
    sendThread.join()
    acceptThread.join()
    handlerThreads.join()


#handle .env as global variable, outside of scope all all methods
#parse and validate .env, then call main()
env = dotenv_values('.env')

if len(sys.argv) < 2:
    print("You must provide the client's ip, exiting...")
    exit()
env['CLIENT_LISTEN_IP'] = sys.argv[1]

print('Combined env and argv config:', dict(env))
if not validateEnv(env):
    print('.env failed validation, exiting...')
    exit()

#to be used in our vector clocks as the process identifier
#e.g. [UUID-AAAAAA   1]
#     [UUID-BBBBBB   2]
#and so on
processId = str(uuid.uuid4()) 
main()