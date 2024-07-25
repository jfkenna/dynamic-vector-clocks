from threading import Thread, Lock, Event
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from shared.env_handler import loadArgsAndEnvClient, getPeerNames
from shared.client_message import constructMessage, constructHello, constructHelloResponse, parseJsonMessage, messageToJson, MessageType
from shared.server_message import RegistryMessageType, constructBasicMessage
from shared.vector_clock import canDeliver, deliverMessage, handleMessageQueue, incrementVectorClock
from shared.network import continueRead, readSingleMessage, silentFailureClose, sendToSingleAdr, buildNetworkEntry
from GUI_components import GUI, textUpdateGUI, statusUpdateGUI, updateLivePeerCountGUI
from kivy.lang import Builder
from kivy.app import App
import socket
import uuid
import sys
import time
import selectors
import copy
import json

#************************************************************
#Worker threads

#worker thread for accepting incoming connections
#creates new network entries representing the connection
def acceptWorker(serverSocket, peers):
    serverSocket.settimeout(0.1)
    while True:
        if shutdownFlag.is_set():
            return
        try:
            newConnection, adr = serverSocket.accept()
        except socket.timeout:
            continue
        
        ip = adr[0]
        newConnection.setblocking(False)
        
        with peersLock:
            networkEntries[ip] = buildNetworkEntry(newConnection)
            peers.append(ip)
            updateLivePeerCountGUI(len(peers))
        selector.register(newConnection, selectors.EVENT_READ, None)


#worker thread for reading messages from connected sockets
#will read from any socket with available bytes to read
def readWorker(messagesToHandle, peers):
    while True:
        if shutdownFlag.is_set():
            return

        #safely take the next readable socket
        with selectorLock:
            selectResult = selector.select(timeout=0.1)
            if selectResult == []:
                continue
            readableSocket = selectResult[0][0].fileobj
            selector.unregister(readableSocket)
            
        #avoid crash if socket has already closed
        try:
            peer = readableSocket.getpeername()[0]
        except socket.error:
            continue
        networkEntry = networkEntries.get(peer, None)
        if networkEntry == None:
            continue

        #read available messages
        with networkEntry['lock']:
            readfailed = continueRead(networkEntry, messagesToHandle)

        #add socket back to selector if read didn't error out
        if readfailed:
            handlePeerFailure(peer, peers)
        else:
            selector.register(readableSocket, selectors.EVENT_READ, None)
                

#worker thread for broadcasting enqueued messages
#used for sending own messages, and for rebroadcasting messages from other peers
def broadcastWorker(outgoingMessageQueue, receivedMessages, peers):
    global processVectorClock 

    #pass in queue once GUI is ready for binding
    while True:
        if App.get_running_app():
            App.get_running_app().setQueue(outgoingMessageQueue)
            #could do this somewhere else, but fuck it
            with peersLock:
                updateLivePeerCountGUI(len(peers))
            break
        time.sleep(0.005)
    
    #once UI is setup, begin handling broadcasts
    while True:
        if shutdownFlag.is_set():
            return
        try:
            receivedMessage = outgoingMessageQueue.get(timeout=0.1)
        except Empty:
            continue
        
        parsedMessage = parseJsonMessage(receivedMessage, [], False)
        if parsedMessage == None:
            return
        
        #if message originates from UI, hydrate with local clock and processId
        #otherwise, retransmit without changes
        if parsedMessage['sender'] == None:
            receivedMessages[parsedMessage['id']] = True
            with vectorClockLock:
                processVectorClock = incrementVectorClock(processVectorClock, processId)
                outgoingMessage = messageToJson(constructMessage(MessageType.BROADCAST_MESSAGE, processVectorClock, parsedMessage['text'], processId, processIp))
        else:
            outgoingMessage = receivedMessage
        broadcastToPeers(outgoingMessage, peers)


#worker thread for controlling message flow and responding to HELLO/HELLO_RESPONSE messages
#passes off rebroadcast tasks to the broadcast worker
def handlerWorker(messagesToHandle, receivedMessages, delayedMessages, outgoingMessageQueue, peers, preInitialisedReceivedMessages):
    while True:
        if shutdownFlag.is_set():
            return
        try:
            messageInfo = messagesToHandle.get(timeout=0.1)
        except Empty:
            continue

        message = parseJsonMessage(messageInfo[1], [], True)
        if message == None:
            print("[ERR] Got bad message")
            continue

        peerNetworkData = messageInfo[0]

        #ADDITION FOR DEMONSTRATION
        #NOT REQUIRED FOR APP TO FUNCTION
        #SIMULATES NETWORK DELAY BY ADDING MESSAGES TO THE QUEUE AFTER 5 SECONDS HAVE PASSED
        if int(env['ENABLE_NETWORK_DELAY']) == 1 and message['type'] == MessageType.BROADCAST_MESSAGE:
            try:
                if message['senderIp'] == env['THROTTLED_IP']:
                    #if we haven't held the message back before, create a new thread
                    #to re-add it back to messages after some time has passed
                    if messageInfo[2] == False:
                        with delayedMessageLock:
                            if delayedMessages.get(message['id'], None) == None:
                                delayedMessages[message['id']] = True
                                print('[INFO] Delaying delivery of message: {0}'.format(message['text']))
                                def delayedDeliveryCallback(messageInfo, messagesToHandle):
                                    time.sleep(int(env['MOCK_NETWORK_DELAY']))
                                    messagesToHandle.put((messageInfo[0], messageInfo[1], True))
                                delayedDeliveryThread = Thread(target=delayedDeliveryCallback, args=(messageInfo, messagesToHandle,))
                                delayedDeliveryThread.start()
                        continue
            except socket.error:
                continue

        #handle messages
        if message['type'] == MessageType.HELLO:
            handleHello(peerNetworkData, message, peers, preInitialisedReceivedMessages)
        if message['type'] == MessageType.HELLO_RESPONSE:
            handleHelloResponse(peerNetworkData, message, preInitialisedReceivedMessages)
        if message['type'] == MessageType.BROADCAST_MESSAGE:
            handleBroadcastMessage(message, receivedMessages, outgoingMessageQueue)
        if message == None:
            print('[ERR] Parse error'.format(id))
            continue

#************************************************************
#Message handlers

#reply to hello messages with copy of own state
def handleHello(networkEntry, message, peers, preInitialisedReceivedMessages):
    global processVectorClock
    global processMessageQueue

    #allow other nodes to initialise by cloning a node with no peers
    #this allows the first connection to be made
    #this scenario can only occur if the hostname of a node that was launched no connections is provided as peer
    if (not initialisationComplete.is_set()) and (not initiallyUnconnected.is_set()):
        print('[ERR] A process attempted to clone this node before it was initialized')
        return
    
    try:
        if networkEntry['connection'] == None:
            return
        peer = networkEntry['connection'].getpeername()[0]
    except socket.error:
        peer = None

    #case where we provide clone data as an unconnected, uninitialized peer
    if (not initialisationComplete.is_set()) and initiallyUnconnected.is_set():
        with vectorClockLock:
            with preInitialisedLock:
                emptyHelloResponse = messageToJson(constructHelloResponse(processId, processIp, processVectorClock, preInitialisedReceivedMessages))
        
        with networkEntry['lock']:
            if sendToSingleAdr(emptyHelloResponse, networkEntry['connection']):
                handlePeerFailure(peer, peers)
                print('[ERR] Failed to send clone data to peer. Remaining unitialised')
                return
        
        #initialise after sending peer data
        with vectorClockLock:
            with preInitialisedLock:
                processVectorClock = handleMessageQueue(processVectorClock, preInitialisedReceivedMessages, None, textUpdateGUI)
        print('[INFO] Initialised with clock {0}'.format(processVectorClock))
        register()
        initialisationComplete.set()
        return

    #case where we provide clone data as an initialised node in the network
    with vectorClockLock:
        helloResponse = messageToJson(constructHelloResponse(processId, processIp, processVectorClock, processMessageQueue))

    with networkEntry['lock']:
        if sendToSingleAdr(helloResponse, networkEntry['connection']):
            handlePeerFailure(peer, peers)
            print('[ERR] Failed to send clone data to peer')
            return


#consume hello response to build initial peer state
#once complete, process is an exact clone of another peer's previous state
def handleHelloResponse(networkEntry, message, preInitialisedReceivedMessages):
    global processVectorClock
    global processMessageQueue

    #discard message if we have already cloned a process
    if initialisationComplete.is_set():
        return
    

    #join messages we captured prior to initialisation with the undelivered messages
    #received from the cloned processes
    with vectorClockLock:
        with preInitialisedLock:
            processMessageQueue = message['undeliveredMessages'] + preInitialisedReceivedMessages
            joinedClock = message['clock'] + processVectorClock #entire received clock + our single clock entry
            processVectorClock = handleMessageQueue(joinedClock, processMessageQueue, None, textUpdateGUI)
            print('[INFO] Initialised with clock {0}'.format(processVectorClock))
            register()
            initialisationComplete.set()
    

#handle broadcast messages received from other processes
#vector clock ensures causal delviery of received broadcasts
def handleBroadcastMessage(message, receivedMessages, outgoingMessageQueue):
    global processVectorClock
    global processMessageQueue

    #avoid double processing messages
    with messageLock:
        if message['id'] in receivedMessages:
            return
        #add to list of received messages
        receivedMessages[message['id']] = True

    #while our setup is incomplete, don't broadcast to peers, and don't attempt to deliver
    #simply enqueue and return - delivery will be handled once setup completes
    with preInitialisedLock:
        if not initialisationComplete.is_set():
            preInitialisedReceivedMessages.append(message)
            return

    #broadcast to other peers (reliable broadcast, so each receipt will broadcast to all other known nodes)
    jsonMessage = messageToJson(message)
    outgoingMessageQueue.put(jsonMessage)

    #if this processId is the sender of the message, don't worry about delivering message
    if not message['sender'] == processId:
        with vectorClockLock:
            if canDeliver(processVectorClock, message):
                processVectorClock = deliverMessage(processVectorClock, message, processId, textUpdateGUI)
            else:
                processMessageQueue.append(message)

            processVectorClock = handleMessageQueue(processVectorClock, processMessageQueue, message, textUpdateGUI)


#************************************************************
#Network / communication helpers

#constructs socket for establishing initial connection to another peer
def buildSenderSocket():
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    senderSocket.bind((env['CLIENT_LISTEN_IP'], 0)) #bind to specific sender adr so we can receive replies
    senderSocket.settimeout(0.25)
    return senderSocket


#sends a single message to all peers
def broadcastToPeers(message, peers):

    #clone peer list so that multiple workers to broadcast different messages
    #simultaneously (e.g. one thread retransmitting broadcast, one thread sending new message) 
    with peersLock:
        currentPeers = copy.deepcopy(peers)
    
    for peer in currentPeers:
        networkEntry = networkEntries[peer]
        if networkEntry == None or networkEntry['connection'] == None:
            continue
        
        with networkEntry['lock']:
            sendFailed = sendToSingleAdr(message, networkEntry['connection'])

        if sendFailed:
            handlePeerFailure(peer, peers)

#helper, used to update peer list and network info when a peer's connection fails
#if peers fall to 0, triggers the display of a warning message
def handlePeerFailure(peer, peers):
    print('[ERR] Connection with {0} failed. Removing from peer list'.format(peer))
    with peersLock:
        networkEntry = networkEntries.get(peer, None)
        if networkEntry == None:
            return
        connection = networkEntry['connection']
        del networkEntries[peer]
        peers.remove(peer)
        silentFailureClose(connection)
        remainingPeers = len(peers)
        updateLivePeerCountGUI(remainingPeers)

        #If there was some point in time where we were not connected to any peers
        #we might have missed all broadcasts of a message, so all messages that were causally linked to that message
        #can never be delivered. It's important to flag to the user that we may be in that state
        #so they know that it's possible they may never receive another message, and can decide to restart.
        #
        #In a real application, it would make sense to shut the app completely
        #but as this is a demo, it's better to show we are able to detect this type of failure
        if remainingPeers == 0:
            statusUpdateGUI('NEW MESSAGES MAY NOT HAVE BEEN RECEIVED', True)
            print('[INFO] Temporarily severed from all peers - future received messages may be undeliverable')


#************************************************************
#Setup helpers

#registers peer with registry server
#returns True if registration succeeded, False otherwise
def register():
    if int(env['ENABLE_PEER_SERVER']) == 1:
        try:
            serverAdr = socket.gethostbyname(env['PEER_REGISTRY_IP'])
        except:
            print('[ERR] Couldn\'t resolve registry server hostname. Your peers will need to add you manually.')

        registerMessage = messageToJson(constructBasicMessage(RegistryMessageType.REGISTER_PEER))
        
        try:
            senderSocket = buildSenderSocket()
            senderSocket.connect((serverAdr, int(env['REGISTRY_PROTOCOL_PORT'])))
        except socket.error:
            print('[ERR] Failed to register with registry server. Your peers will need to add you manually.')
            return True

        if sendToSingleAdr(registerMessage, senderSocket):
            print('[ERR] Failed to register with registry server. Your peers will need to add you manually.')
            return True
    return False


#helper, enqueues the node's initial HELLO message
def sayHello(peers, outgoingMessageQueue):
    helloMessage = messageToJson(constructHello(processId, processIp))
    #directly broadcast rather than adding to send queue, as the p2p send worker won't start until hello is complete
    broadcastToPeers(helloMessage, peers)


#************************************************************
#App

#handles param setup and starts threads / gui
def main():

    #setup shared fields

    #messages that have been read from a socket and need to be handled
    #[(networkEntry, message, hasAlreadyBeenHeldBack)]
    #hasAlreadyBeenHeldBack is only used for simulating network delay
    messagesToHandle = Queue()

    #messages that need to be broadcast
    #[(message, isRetransmitting)]
    outgoingMessageQueue = Queue()
    
    #message ids that we've already received
    receivedMessages = {}

    #initial message collector, stores messages that arrive before HELLO_RESPONSE arrives
    #ensures no messages are missed even if the channel is not FIFO
    preInitialisedReceivedMessages = []

    #ids of messages whose receipt we've delayed (only used for simulating network delay)
    delayedMessages = {}

    #get peers from peer server or command line based on params
    #room for extension - add new peers at runtime based on received messages, so network is more fault tolerant
    if int(env['ENABLE_PEER_SERVER']) == 1:
        try:
            serverAdr = socket.gethostbyname(env['PEER_REGISTRY_IP'])
        except:
            printAndExit('Failed to resolve registry server hostname')

        print('[INFO] Retrieving peers from registry server...')
        getPeerMessage = messageToJson(constructBasicMessage(RegistryMessageType.GET_PEERS))

        try:
            senderSocket = buildSenderSocket()
            senderSocket.connect((serverAdr, int(env['REGISTRY_PROTOCOL_PORT'])))
        except socket.error:
            printAndExit('Failed to connect to registry server')
        if sendToSingleAdr(getPeerMessage, senderSocket):
            printAndExit('Failed to get peers from registry server')
        try:
            peerResponse = readSingleMessage(senderSocket)
            if peerResponse == None:
                printAndExit('Failed to get peer from registry server')
        except socket.error:
            printAndExit('Failed to get peer from registry server')

        silentFailureClose(senderSocket)
        
        peerData = parseJsonMessage(peerResponse, ['peers', 'type'])
        if peerData == None or peerData['type'] != RegistryMessageType.PEER_RESPONSE:
            printAndExit('Registry responded with an invalid message')

        unconnectedPeers = peerData['peers']
        print('[INFO] Received peers from registry: ', unconnectedPeers)
    else:
        unconnectedPeers = getPeerNames()
    
    #establish connections
    peers = []
    for peer in unconnectedPeers:
        p2pSocket = buildSenderSocket()
        try:
            p2pSocket.connect((peer, int(env['PROTOCOL_PORT'])))
            networkEntries[peer] = buildNetworkEntry(p2pSocket)
            peers.append(peer)
            selector.register(p2pSocket, selectors.EVENT_READ, None)
        except socket.error:
            print('[ERR] Could not establish connection for peer {0}'.format(peer))
            print('[INFO] Removing it from the startup peer list')

    if len(peers) == 0:
        if int(env['ENABLE_PEER_SERVER']) == 1:
            print('[INFO] Registry had no valid peers, registering self')
            register()
        print('[INFO] Starting with no peers - waiting for at least one peer to establish connection...')
        initiallyUnconnected.set()
    
    #create worker threads
    broadcastWorkers = []
    handlerWorkers = []
    readWorkers = []
    for i in range(int(env['CLIENT_WORKER_THREADS'])):
        broadcastWorkers.append(Thread(target=broadcastWorker, args=(outgoingMessageQueue, receivedMessages, peers)))
        handlerWorkers.append(Thread(target=handlerWorker, args=(messagesToHandle, receivedMessages, 
            delayedMessages, outgoingMessageQueue, peers, preInitialisedReceivedMessages)))
        readWorkers.append(Thread(target=readWorker, args=(messagesToHandle, peers, )))
    for i in range(int(env['CLIENT_WORKER_THREADS'])):
        broadcastWorkers[i].start()
        handlerWorkers[i].start()
        readWorkers[i].start()

    #setup listener
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((env['CLIENT_LISTEN_IP'], int(env['PROTOCOL_PORT'])))
    acceptSocket.listen()
    print('[INFO] Client listening at {0} on port {1}'.format(env['CLIENT_LISTEN_IP'], env['PROTOCOL_PORT']))
    acceptThread = Thread(target=acceptWorker, args=(acceptSocket, peers))
    acceptThread.start()


    #clone state of some other node in the network as own initial state
    if len(peers) > 0:
        sayHello(peers, outgoingMessageQueue)
        print('[INFO] Connecting to the network, please wait...')

    #don't start the GUI until hello completes
    while not initialisationComplete.is_set():
        time.sleep(0.1)

    #start GUI from template file
    Builder.load_file('GUI.kv')
    GUI(title='CHAT CLIENT [{0}]'.format(env['CLIENT_LISTEN_IP'])).run()

    print('[INFO] GUI closed, terminating threads...')
    shutdownFlag.set()
    for worker in broadcastWorkers:
        worker.join()
    print('[INFO] Joined broadcasters...')
    for worker in readWorkers:
        worker.join()
    print('[INFO] Joined readers...')
    for worker in handlerWorkers:
        worker.join()
    print('[INFO] Joined handlers...')
    acceptThread.join()
    silentFailureClose(acceptSocket)
    print('[INFO] All threads closed... exiting...')
    
#print helper
def printAndExit(message):
    print('[ERR] ' + message)
    print('exiting...')
    exit()

#************************************************************
#setup env

env = loadArgsAndEnvClient(sys.argv)
print('App configuration (.env + argv):', json.dumps(dict(env), indent=4))

#************************************************************
#state

#maps a peer --> object containing peer socket, socket lock, current message size, read buffer
networkEntries = {}

#read socket selector
selector = selectors.DefaultSelector()

#************************************************************
#global locks for thread synchronisation

#p2p state locks
peersLock = Lock() #lock for peers list
messageLock = Lock() #lock for received message dict
preInitialisedLock = Lock() #lock for pre-initialisation message queue

#lock for socket selector (used to select next READABLE socket)
selectorLock = Lock()

#lock for incrementing and reading vector clock
vectorClockLock = Lock()

#lock for accessing delayed message dict - only used for simulating network delay
delayedMessageLock = Lock()

#************************************************************
#events

#shutdown event, flags that threads should close
shutdownFlag = Event()

#initialisation complete event, flags that cloning is complete and node is part of network
initialisationComplete = Event()

#flags if a peer was initialised with no connections
#used to determine if a node should be allowed to clone the peer if the peer is not initialised
initiallyUnconnected = Event()

#************************************************************
#vector clock and causal message queue

processIp = env['CLIENT_LISTEN_IP']
processId = str(uuid.uuid4())
# This process's vector clock - initialised with a UUID e.g.
# [ [FAKE-UUID-EXAMPLE-STRING, 0] ]
processVectorClock = [[processId, 0]]
processMessageQueue = []


main()

'''
Bibliography
[1] N. Meghanathan. Module 6.2.3 Matrix Algorithm Causal Delivery of Messages. (Nov. 12, 2013). Accessed: Mar. 13, 2024. [Online video]. Available: https://www.youtube.com/watch?v=WgTx7BHWzts.
[2] T. Landes. "Dynamic Vector Clocks for Consistent Ordering of Events in Dynamic Distributed Applications." in International Conference on Parallel and Distributed Processing Techniques and Applications, Las Vegas, Nevada, USA, 2006, pp.1-7.
[3] L. Lafayette. (2021). The Spartan HPC System at the University of Melbourne [PDF]. Available: https://canvas.lms.unimelb.edu.au/courses/105440/files/7018506/download?download_frd=1.
[4] L. Dalcin. "Tutorial". MPI for Python. https://mpi4py.readthedocs.io/en/stable/tutorial.html (accessed Mar. 13, 2024).
[5] Jurudocs. "Format a datetime into a string with milliseconds". Stack Overflow. https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds (accessed Mar. 13, 2024).
[6] M. Toboggan. "How to get a random number between a float range?". Stack Overflow. https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range (accessed Mar. 15, 2024).
[7] NumPy Developers. "numpy.zeros". NumPy. https://numpy.org/doc/stable/reference/generated/numpy.zeros.html (accessed Mar. 16, 2024).
[8] New York University. "Non-blocking Communication". GitHub Pages. https://nyu-cds.github.io/python-mpi/03-nonblocking/ (accessed Mar. 24, 2024).
[9] L. Dalcin. "mpi4py.MPI.Message". MPI for Python. https://mpi4py.readthedocs.io/en/stable/reference/mpi4py.MPI.Message.html (accessed Mar. 30, 2024).
[10] W3Schools. "Python String split() Method". W3Schools. https://www.w3schools.com/python/ref_string_split.asp (accessed Mar. 30, 2024).
[11] C. Kolade. "Python Switch Statement - Switch Case Example". freeCodeCamp. https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ (accessed Mar. 30, 2024).
[12] spiderman. "How to find string that start with one letter then numbers". FME Community. https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 (accessed Mar. 30, 2024).
[13] TutorialsTeacher. "Grouping in Regex". TutorialsTeacher. https://www.tutorialsteacher.com/regex/grouping (accessed Mar. 30, 2024).
[14] hoju. "Extract part of a regex match". Stack Overflow. https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match (accessed Mar. 30, 2024).
[15] M. Breuss. "How to Check if a Python String Contains a Substring". Real Python. https://realpython.com/python-string-contains-substring/ (accessed Mar. 30, 2024).
[16] Python Principles. "How to convert a string to int in Python". Python Principles. https://pythonprinciples.com/blog/python-convert-string-to-int/ (accessed Mar. 30, 2024).
[17] TransparenTech LLC. "Generate a UUID in Python". UUID Generator. https://www.uuidgenerator.net/dev-corner/python/ (accessed Mar. 30, 2024).
[18] W3Schools. "Python - List Comprehension". W3Schools. https://www.w3schools.com/python/python_lists_comprehension.asp (accessed Mar. 30, 2024).
[19] greye. "Get loop count inside a for-loop [duplicate]". Stack Overflow. https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop (accessed Mar. 30, 2024).
[20] G. Ramuglia. "Using Bash to Count Lines in a File: A File Handling Tutorial". I/O Flood. https://ioflood.com/blog/bash-count-lines/ (accessed Mar. 30, 2024).
[21] H. Sundaray. "How to Use Bash Getopts With Examples". KodeKloud. https://kodekloud.com/blog/bash-getopts/ (accessed Mar. 30, 2024).
[22] Linuxize. "Bash Functions". Linuxize. https://linuxize.com/post/bash-functions/ (accessed Mar. 30, 2024).
[23] Nick. "How can I add numbers in a Bash script?". Stack Overflow. https://stackoverflow.com/questions/6348902/how-can-i-add-numbers-in-a-bash-script (accessed Mar. 30, 2024).
[24] GeeksForGeeks. "Command Line Arguments in Python". GeeksForGeeks. https://www.geeksforgeeks.org/command-line-arguments-in-python/ (accessed Mar. 30, 2024).
[25] V. Hule. "Generate Random Float numbers in Python using random() and Uniform()". PYnative. https://pynative.com/python-get-random-float-numbers/ (accessed Apr. 1, 2024).
[26] bhaskarc. "Iterating over a 2 dimensional python list [duplicate]". Stack Overflow. https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list (accessed Apr. 1, 2024).
[27] note.nkmk.me. "How to return multiple values from a function in Python". note.nkmk.me. https://note.nkmk.me/en/python-function-return-multiple-values/ (accessed Apr. 2, 2024).
[28] A. Luiz. "How do you extract a column from a multi-dimensional array?". Stack Overflow. https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array (accessed Apr. 2, 2024).
[29] W3Schools. "Python Remove Array Item". W3Schools. https://www.w3schools.com/python/gloss_python_array_remove.asp (accessed Apr. 2, 2024).
[30] nobody. "Python regular expressions return true/false". Stack Overflow. https://stackoverflow.com/questions/6576962/python-regular-expressions-return-true-false (accessed May. 6, 2024).
[31] A. Jalli. "Python Switch Case -- Comprehensive Guide". Medium. https://medium.com/@artturi-jalli/python-switch-case-9cd0014759e4 (accessed May. 4, 2024).
[32] Linuxize. "Bash if..else Statement". Linuxize. https://stackoverflow.com/questions/67428689/how-to-pass-multiple-flag-and-multiple-arguments-in-getopts-in-shell-script (accessed May. 4, 2024).
[33] Kivy. "Kivy: The Open Source Python App Development Framework.". Kivy. https://kivy.org/ (accessed May. 4, 2024).
[34] R. Strahl. "Getting Images into Markdown Documents and Weblog Posts with Markdown Monster". Medium. https://medium.com/markdown-monster-blog/getting-images-into-markdown-documents-and-weblog-posts-with-markdown-monster-9ec6f353d8ec (accessed May. 5, 2024).
'''