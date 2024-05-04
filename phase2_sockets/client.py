from threading import Thread, Lock, Event
from queue import Queue
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor
from shared.validator import validateEnv
from shared.client_message import constructMessage, constructHello, constructHelloResponse, parseJsonMessage, messageToJson, MessageType
from shared.server_message import RegistryMessageType, constructBasicMessage
from shared.vector_clock import canDeliver, deliverMessage, handleMessageQueue, incrementVectorClock
from shared.network import sendWithHeaderAndEncoding, readSingleMessage
import socket
import uuid
import sys
import time

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
        outgoingMessage = messageToJson(constructMessage(MessageType.BROADCAST_MESSAGE, processVectorClock, outgoingMessageText, processId))
        broadcastToPeers(outgoingMessage, peers)

def networkWorker(connectionQueue, receivedMessages, preInitialisedReceivedMessages, peers, id):
    print('[w{0}] Started'.format(id))
    global processVectorClock
    global processMessageQueue
    while True:
        connection, adr = connectionQueue.get()
        try:
            #attempt to read a single message from the connection
            data = readSingleMessage(connection)

            #socket closed before full message length was read
            if data == None:
                print('Error reading from socket - connection closed before full header length could be read')
                silentFailureClose(connection)
                continue

        except socket.error:
            print('Error reading from socket: {0}'.format(socket.error))
            print('Closing the connection without attempting to read more')
            silentFailureClose(connection)
            continue
        
        requestingPeer = connection.getpeername()[0]
        silentFailureClose(connection)
        message = parseJsonMessage(data, [], True)

        if message == None:
            print('[w{0}] Parse error'.format(id))
            continue

        #special handling for hello messages
        if message['type'] == MessageType.HELLO:

            #allow other nodes to initialise by cloning a node with no peers
            #this allows the first connection to be made
            #this scenario can only occur if the hostname of a node that was launched no connections is provided as peer
            if (not initialisationComplete.is_set()) and (not initiallyUnconnected.is_set()):
                print('A process attempted to clone this node before it was initialized')
                return
            
            #case where we provide clone data as an unconnected, uninitialized peer
            #TODO triple check there is no case where this can cause perma-wait issues
            #in scenarios where 'HELLO' is broadcast to both a real peer that is sending messages, and an unconnected peer

            if (not initialisationComplete.is_set()) and initiallyUnconnected.is_set():
                emptyHelloResponse = messageToJson(constructHelloResponse(processId, processVectorClock, preInitialisedReceivedMessages))


                senderSocket = buildSenderSocket()
                #don't initialise if peer couldn't receive message
                if sendToSingleAdr(emptyHelloResponse, senderSocket, requestingPeer, int(env['PROTOCOL_PORT'])):
                    print('Failed to send clone data to peer. Remaining unitialised')
                    continue
                silentFailureClose(senderSocket)
                
                #initialise after sending peer data
                peers.append(requestingPeer) #TODO see comment below on need for lock on peers - very important to address
                handleMessageQueue(processVectorClock, preInitialisedReceivedMessages, None) #TODO double check if necessary for this empty case
                registerAndCompleteInitialisation()
                continue

            #TODO need to lock on vector clock and message queue here
            #i think i'll just make a monitor class to simplify all these locks
            #for now, don't even lock, just so basic functionality is present
            helloResponse = messageToJson(constructHelloResponse(processId, processVectorClock, processMessageQueue))
            senderSocket = buildSenderSocket()
            sendToSingleAdr(helloResponse, senderSocket, requestingPeer, int(env['PROTOCOL_PORT']))
            silentFailureClose(senderSocket)

            #TODO I think a lock is required for the case where we are iterating over peers at the same time
            #the new peer is added - we might not send one of the messages to the new peer, causing dropped messages
            #so all sending should stop until we finish handling the 'HELLO' and adding the peer.
            #also need to think about the case where messages are in process of being sent by another thread so are not in enqueued messages, but are also not sent to peer
            peers.append(requestingPeer)
            continue

        #special handling for hello responses
        if message['type'] == MessageType.HELLO_RESPONSE:

            print('GOT HELLO RESPONSE')

            #discard message if we have already cloned a process
            if initialisationComplete.is_set():
                continue

            #join messages we captured prior to initialisation with the undelivered messages
            #received from the cloned processes
            with preInitialisedLock:
                processVectorClock = message['clock']
                clonedMessages = message['undeliveredMessages']
                clonedMessages = clonedMessages + preInitialisedReceivedMessages
                processMessageQueue = clonedMessages
                handleMessageQueue(processVectorClock, processMessageQueue, None)
                registerAndCompleteInitialisation()
            continue

        #handle standard messages
        handleMessage(message, receivedMessages, peers)


def UIWorker(outgoingMessageQueue):
    print('===CHAT STARTED=======')
    while True:
        newMessageText = input()
        outgoingMessageQueue.put(newMessageText)


def handleMessage(message, receivedMessages, peers):

    with messageLock:
        if message['id'] in receivedMessages:
            return
        #add to list of received messages
        receivedMessages[message['id']] = True

    #while our setup is incomplete, don't broadcast to peers, and don't attempt to deliver
    #simply enqueue and return - delivery will be handled once setup completes
    #TODO triple check there's no flow where messages can be missed here
    #i think the lock order is OK, but confirmation is always nice
    with preInitialisedLock:
        if not initialisationComplete.is_set():
            preInitialisedReceivedMessages.append(message)
            return


    global processVectorClock
    global processMessageQueue

    
    #print("Sender:",message["sender"])
    #print("Receiver:",processId)
    #print(processVectorClock)
    #broadcast to other peers (reliable broadcast, so each receipt will broadcast to all other known nodes)
    jsonMessage = messageToJson(message)
    broadcastToPeers(jsonMessage, peers)
    # If this processId is the sender of the message
    if not message["sender"] == processId:
        #print("Deliver/update the VC of the receiver if causality met?")
        if canDeliver(processVectorClock, message):
            #print("initial process VC", processVectorClock)
            processVectorClock = deliverMessage(processVectorClock, message, processId)
        else:
            processMessageQueue.append(message)

        processVectorClock = handleMessageQueue(processVectorClock, processMessageQueue, message)


def registerAndCompleteInitialisation():
    if int(env['ENABLE_PEER_SERVER']) == 1:
        try:
            serverAdr = socket.gethostbyname(env['PEER_REGISTRY_IP'])
        except:
            print('Registration failed due to issues resolving the registry server hostname')
            print('Your peers will need to add you manually.')

        registerMessage = messageToJson(constructBasicMessage(RegistryMessageType.REGISTER_PEER))
        senderSocket = buildSenderSocket()
        if sendToSingleAdr(registerMessage, senderSocket, serverAdr, int(env['REGISTRY_PROTOCOL_PORT'])):
            print('Failed to register with registry server. Your peers will need to add you manually.')
    initialisationComplete.set()


def buildSenderSocket():
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    senderSocket.bind((env['CLIENT_LISTEN_IP'], 0)) #bind to specific sender adr so we can receive replies
    senderSocket.settimeout(0.25) #250 ms maximum timeout - allows reasonable amounts of network delay
    return senderSocket

def sendToSingleAdr(message, senderSocket, adr, port):
    try:
        senderSocket.connect((adr, port))
    except socket.error:
        print('Error connecting to adr: {0}'.format(socket.error))
        return True
    try:
        sendWithHeaderAndEncoding(senderSocket, message)
    except socket.error:
        print('Error sending message to peer: {0}'.format(socket.error))
        return True
    return False


def broadcastToPeers(message, peers):
    failedCount = 0
    for peer in peers:
        #print("Broadcasting to peer {0}".format(peer))
        #print("trying with peer {0}".format(peer))
        senderSocket = buildSenderSocket()
        if sendToSingleAdr(message, senderSocket, peer, int(env['PROTOCOL_PORT'])):
            failedCount += 1
        silentFailureClose(senderSocket)
        #print('broadcast {0} to {1}'.format(message, peer))
    
    if (failedCount == len(peers)):
        #TODO decide on error handling here
        #maybe try to get a new set of peers from the server, and if that also fails, close completely?
        print('Failed to broadcast message to any of our peers. We may be disconnected from the network...')
        return True
    return False



def getPeerHosts():
    initialPeers = []
    print("Enter peer IPs/hostnames [enter \'finished\' or \'f\' to continue]")
    while True:
        peer = input('Enter hostname: ')
        if peer == 'finished' or peer == 'f':
            if (len(initialPeers) == 0):
                confirm = input('Confirm that you intend to start peer unconnected [Y to confirm, or anything else to cancel]...')
                if confirm == 'Y':
                    return initialPeers
                continue
            return initialPeers
        try:
            resolvedAdr = socket.gethostbyname(peer)
            initialPeers.append(resolvedAdr)
            print('Added peer at {0}'.format(resolvedAdr))
        except:
            print('Couldn\'t resolve hostname, enter a different value')
            continue


def sayHello(peers):
    helloMessage = messageToJson(constructHello(processId))
    if broadcastToPeers(helloMessage, peers):
        #TODO also need logic to handle the case where peer receives request but never replies
        #could be handled with a timer. But to be honest, this server logic is growing really complex
        print('Failed to send HELLO message to any of our peers. Registering and starting with an empty clock')
        registerAndCompleteInitialisation()

def main():

    #create shared resources
    #suprisingly, default python queue is thread-safe and blocks on .get()
    connectionQueue = Queue()
    outgoingMessageQueue = Queue()
    
    #use with 'messageLock' to ensure mutex
    receivedMessages = {}

    #initial message collector (use while hello call is in-flight)
    #use with 'preInitialisedLock' to ensure mutex
    preInitialisedReceivedMessages = []

    #TODO consider adding new peers at runtime based on received messages, so network is more fault tolerant
    #it's very brittle right now - if you add a single peer that only knows one other peer, it's a network partition waiting to happen
    #this is an extension, so for our first implementation just start with a fixed set of peers that we can multicast to


    #get peers from peer server or command line based on params
    if int(env['ENABLE_PEER_SERVER']) == 1:
        try:
            serverAdr = socket.gethostbyname(env['PEER_REGISTRY_IP'])
        except:
            print('Failed to resolve registry server hostname')
            print('exiting...')
            exit()

        print('Retrieving peers from registry server...')
        getPeerMessage = messageToJson(constructBasicMessage(RegistryMessageType.GET_PEERS))
        senderSocket = buildSenderSocket()
        if sendToSingleAdr(getPeerMessage, senderSocket, serverAdr, int(env['REGISTRY_PROTOCOL_PORT'])):
            print('Failed to get peers from registry server')
            print('exiting...')
            exit()

        try:
            peerResponse = readSingleMessage(senderSocket)
            if peerResponse == None:
                print('Failed to get peer from registry server')
                print('exiting...')
                exit()
        except socket.error:
            print('Failed to get peer from registry server')
            print('exiting...')
            exit()

        silentFailureClose(senderSocket)
        
        peerData = parseJsonMessage(peerResponse, ['peers', 'type'])
        if peerData == None or peerData['type'] != RegistryMessageType.PEER_RESPONSE:
            print('Registry responded with an invalid message')
            print('exiting...')
            exit()
        peers = peerData['peers']
        print('Received peers from registry: ', peers)
        if (len(peers) == 0):
            print('Registry had no peers, registering self')
            registerAndCompleteInitialisation()
    else:
        peers = getPeerHosts()
        if len(peers) == 0:
            initiallyUnconnected.set()
    
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
        worker = Thread(target=networkWorker, args=(connectionQueue, receivedMessages, preInitialisedReceivedMessages, peers, i, ))
        handlerThreads.append(worker)
        worker.start()

    #thread for self-initiated messages
    sendThread = Thread(target=sendWorker, args=(outgoingMessageQueue, peers, processId))
    sendThread.start()

    #clone state of some other node in the network as own initial state
    if len(peers) > 0:
        sayHello(peers)
        print('connecting to the network, please wait...')
    else:
        print('waiting for at least one other peer to establish connection...')

    #don't start the input thread until hello completes
    while not initialisationComplete.is_set():
        time.sleep(0.1)

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
if not validateEnv(env, ['PROTOCOL_PORT', 'CLIENT_WORKER_THREADS', 'REGISTRY_PROTOCOL_PORT', 'ENABLE_PEER_SERVER', 'ENABLE_NETWORK_DELAY']):
    print('.env failed validation, exiting...')
    exit()

if len(sys.argv) < 2:
    print("You must provide the client's ip, exiting...")
    exit()
env['CLIENT_LISTEN_IP'] = sys.argv[1]

if int(env['ENABLE_PEER_SERVER']) == 1 and len(sys.argv) < 3:
    print("ENABLE_PEER_SERVER flag was set, but you did not provide the ip of a peer registry")
    print("exiting...")
    exit()

if (int(env['ENABLE_PEER_SERVER']) == 1):
    env['PEER_REGISTRY_IP'] = sys.argv[2]

print('Combined env and argv config:', dict(env))

#global lock for received message dict
messageLock = Lock()

#global lock for pre-initialisation message queue
preInitialisedLock = Lock()

#initialisation complete event
initialisationComplete = Event()

#flag for if peer was initialised with no connections
#used to determine if a node should be allowed to clone it, despite it not being initialised
initiallyUnconnected = Event()

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