from threading import Thread
from queue import Queue
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor
from shared.validator import validateEnv
from shared.client_message import constructMessage, parseJsonMessage, messageToJson, MessageType
from shared.vector_clock import canDeliver, deliverMessage, handleMessageQueue, incrementVectorClock
import socket
import uuid
import sys

def silentFailureClose(connection):
    try:
        connection.close()
    except:
        pass

def acceptWorker(connectionQueue, serverSocket):
    print('[a0] Started')
    while True:
        connectionQueue.put(serverSocket.accept())
        #print('[a0] Accepted connection')


def sendWorker(outgoingMessageQueue, peers, processId):
    print('[s0] Started')
    while True:
        outgoingMessageText = outgoingMessageQueue.get()
        global processVectorClock 
        processVectorClock = incrementVectorClock(processVectorClock, processId)
        outgoingMessage = constructMessage(MessageType.BROADCAST_MESSAGE, processVectorClock, outgoingMessageText, processId)
        broadcastToPeers(outgoingMessage, peers)

def networkWorker(connectionQueue, receivedMessages, peers, id):
    print('[w{0}] Started'.format(id))
    while True:
        connection, adr = connectionQueue.get()
        try:
            #TODO properly read until seperator is reached
            #for now, just assume total message size will be < 1024
            data = connection.recv(100000)
        except socket.error:
            print('Error reading from socket: {0}'.format(socket.error))
            print('Closing the connection without attempting to read more')
            silentFailureClose(connection)
            continue
        
        message = parseJsonMessage(data, ['type', 'clock', 'text', 'sender', 'id'])
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
    global processVectorClock
    global processMessageQueue
    if message['id'] in receivedMessages:
        return
    #add to list of received messages
    receivedMessages[message['id']] = True
    
    #print("Sender:",message["sender"])
    #print("Receiver:",processId)
    #print(processVectorClock)
    #broadcast to other peers (reliable broadcast, so each receipt will broadcast to all other known nodes)
    broadcastToPeers(message, peers)
    # If this processId is the sender of the message
    if not message["sender"] == processId:
        #print("Deliver/update the VC of the receiver if causality met?")
        if canDeliver(processVectorClock, message):
            #print("initial process VC", processVectorClock)
            processVectorClock = deliverMessage(processVectorClock, message, processId)
        else:
            processMessageQueue.append(message)

        processVectorClock = handleMessageQueue(processVectorClock, processMessageQueue, message)

def broadcastToPeers(message, peers):
    jsonMessage = messageToJson(message)
    failedCount = 0
    for peer in peers:
        #print("Broadcasting to peer {0}".format(peer))
        #print("trying with peer {0}".format(peer))

        targetSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        targetSocket.settimeout(0.25) #250 ms maximum timeout - allows reasonable amounts of network delay
        try:
            connection = targetSocket.connect((peer, int(env['PROTOCOL_PORT'])))
        except socket.error:
            failedCount += 1
            print('Error connecting to peer: {0}'.format(socket.error))
            continue
        try:
            targetSocket.send(jsonMessage.encode('utf-8'))
        except socket.error:
            failedCount += 1
            print('Error sending message to peer: {0}'.format(socket.error))
            silentFailureClose(connection)
            continue
        silentFailureClose(connection)
        #print('broadcast {0} to {1}'.format(jsonMessage, peer))
    
    if (failedCount == len(peers)):
        #TODO decide on error handling here
        #maybe try to get a new set of peers from the server, and if that also fails, close completely?
        print('Failed to broadcast message to any of our peers. We may be disconnected from the network...')



def getPeerHosts():
    initialPeers = []
    print("Enter peer IPs/hostnames [enter \'finished\' or \'f\' to continue]")
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
    print("Process ID is", processId)
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


#handle .env as global variable
#parse and validate, then call main()
env = dotenv_values('.env')

if len(sys.argv) < 2:
    print("You must provide the client's ip, exiting...")
    exit()
env['CLIENT_LISTEN_IP'] = sys.argv[1]

print('Combined env and argv config:', dict(env))
if not validateEnv(env, ['PROTOCOL_PORT', 'CLIENT_WORKER_THREADS', 'PROTOCOL_PORT_SERVER', 'ENABLE_PEER_SERVER', 'ENABLE_NETWORK_DELAY']):
    print('.env failed validation, exiting...')
    exit()

#to be used in our vector clocks as the process identifier
#e.g. [UUID-AAAAAA   1]
#     [UUID-BBBBBB   2]
#and so on
processId = str(uuid.uuid4()) 
# This process's vector clock - initialised with its UUID/0 i.e 
# [ [UUID-AAAAA0, 0] ]
processVectorClock = [[processId, 0]]
processMessageQueue = []
# Main 
main()