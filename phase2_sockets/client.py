from threading import Thread, Lock, Event
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from shared.env_handler import loadArgsAndEnvClient
from shared.client_message import constructMessage, constructHello, constructHelloResponse, parseJsonMessage, messageToJson, MessageType
from shared.server_message import RegistryMessageType, constructBasicMessage
from shared.vector_clock import canDeliver, deliverMessage, handleMessageQueue, incrementVectorClock
from shared.network import continueRead, silentFailureClose, sendToSingleAdr, buildNetworkEntry
from GUI_components import GUI, textUpdateGUI, statusUpdateGUI, updateLivePeerCountGUI
from kivy.lang import Builder
from kivy.app import App
import socket
import uuid
import sys
import time
import selectors
import copy

#************************************************************
#worker thread for accepting incoming connections
#creates new network entries representing the connection
def acceptWorker(serverSocket, peers):
    print('[a0] Started')
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


#************************************************************
#worker thread for reading messages from connected sockets
#will read from any socket with available bytes to read
def readWorker(messagesToHandle, peers):
    while True:
        if shutdownFlag.is_set():
            return
        selectResult = selector.select(timeout=0.1)
        if selectResult == []:
            continue

        #https://docs.python.org/3/library/selectors.html
        for key, mask in selectResult:
            if shutdownFlag.is_set():
                return
            
            readableSocket = key.fileobj
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
            if readfailed:
                handlePeerFailure(peer, peers)
                

#************************************************************
#worker thread for broadcasting enqueued messages
#used for sending own messages, and for rebroadcasting messages from other peers
def broadcastWorker(outgoingMessageQueue, receivedMessages, peers, processId):
    global processVectorClock 
    print('[s0] Started')

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
        

        #ugly, but fix if we have time TODO
        parsedMessage = parseJsonMessage(receivedMessage, [], False)
        if parsedMessage == None:
            return
        
        #if message originates from UI, hydrate with local clock and processId
        #otherwise, retransmit without changes
        if parsedMessage['sender'] == None:
            receivedMessages[parsedMessage['id']] = True
            with incrementLock:
                processVectorClock = incrementVectorClock(processVectorClock, processId)
                outgoingMessage = messageToJson(constructMessage(MessageType.BROADCAST_MESSAGE, processVectorClock, parsedMessage['text'], processId))
        else:
            outgoingMessage = receivedMessage
        broadcastToPeers(outgoingMessage, peers)


#************************************************************
#worker thread for controlling message flow and responding to HELLO/HELLO_RESPONSE messages
#passes off rebroadcast tasks to the broadcast worker
def handlerWorker(messagesToHandle, receivedMessages, outgoingMessageQueue):
    while True:
        if shutdownFlag.is_set():
            return
        try:
            messageInfo = messagesToHandle.get(timeout=0.1)
        except Empty:
            continue

        message = parseJsonMessage(messageInfo[1], [], True)
        if message == None:
            print("Got bad message")
            continue

        peerNetworkData = messageInfo[0]

        #ADDITION FOR DEMONSTRATION
        #SIMULATES NETWORK DELAY BY ADDING MESSAGES TO THE QUEUE AFTER 5 SECONDS HAVE PASSED
        if int(env['ENABLE_NETWORK_DELAY']) == 1 and message['type'] == MessageType.BROADCAST_MESSAGE:
            try:
                if message['sender'] == env['THROTTLED_IP']:
                    #if we haven't held the message back before, create a new thread
                    #to re-add it back to messages after some time has passed
                    if messageInfo[2] == False:
                        print('Delaying delivery of message: {0}'.format(message))
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
            handleHello(peerNetworkData, message)
        if message['type'] == MessageType.HELLO_RESPONSE:
            handleHelloResponse(peerNetworkData, message)
        if message['type'] == MessageType.BROADCAST_MESSAGE:
            handleBroadcastMessage(message, receivedMessages, outgoingMessageQueue)
        if message == None:
            print('[w{0}] Parse error'.format(id))
            continue


#************************************************************
#reply to hello messages with copy of own state
def handleHello(networkEntry, message):
    #allow other nodes to initialise by cloning a node with no peers
    #this allows the first connection to be made
    #this scenario can only occur if the hostname of a node that was launched no connections is provided as peer
    if (not initialisationComplete.is_set()) and (not initiallyUnconnected.is_set()):
        print('A process attempted to clone this node before it was initialized')
        return
    
    try:
        if networkEntry['connection'] == None:
            return
        peer = networkEntry['connection'].getpeername()[0]
    except socket.error:
        peer = None

    #case where we provide clone data as an unconnected, uninitialized peer
    if (not initialisationComplete.is_set()) and initiallyUnconnected.is_set():
        with incrementLock:
            emptyHelloResponse = messageToJson(constructHelloResponse(processId, processVectorClock, preInitialisedReceivedMessages))
        
        with networkEntry['lock']:
            if sendToSingleAdr(emptyHelloResponse, networkEntry['connection']):
                handlePeerFailure(peer, peers)
                print('Failed to send clone data to peer. Remaining unitialised')
                return
        
        #initialise after sending peer data
        handleMessageQueue(processVectorClock, preInitialisedReceivedMessages, None, textUpdateGUI) #TODO double check if necessary for this empty case
        registerAndCompleteInitialisation()
        return

    #case where we provide clone data as an initialised node in the network
    with incrementLock:
        helloResponse = messageToJson(constructHelloResponse(processId, processVectorClock, processMessageQueue))

    with networkEntry['lock']:
        if sendToSingleAdr(helloResponse, networkEntry['connection']):
            handlePeerFailure(peer, peers)
            print('Failed to send clone data to peer')
            return


#************************************************************
#consume hello response to build initial peer state
#once complete, process is an exact clone of another peer's previous state
def handleHelloResponse(networkEntry, message):
    #discard message if we have already cloned a process
    if initialisationComplete.is_set():
        return

    #join messages we captured prior to initialisation with the undelivered messages
    #received from the cloned processes
    with preInitialisedLock:
        processVectorClock = message['clock']
        clonedMessages = message['undeliveredMessages']
        clonedMessages = clonedMessages + preInitialisedReceivedMessages
        processMessageQueue = clonedMessages
        handleMessageQueue(processVectorClock, processMessageQueue, None)
        registerAndCompleteInitialisation()
    

#************************************************************
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
        with deliverabilityLock:
            if canDeliver(processVectorClock, message):
                processVectorClock = deliverMessage(processVectorClock, message, processId, textUpdateGUI)
            else:
                processMessageQueue.append(message)

            processVectorClock = handleMessageQueue(processVectorClock, processMessageQueue, message, textUpdateGUI)



#************************************************************
#completes peer setup by
#1. registering with the peer server if it's enabled
#2. flagging that peer initialisation is complete
def registerAndCompleteInitialisation():
    if int(env['ENABLE_PEER_SERVER']) == 1:
        try:
            serverAdr = socket.gethostbyname(env['PEER_REGISTRY_IP'])
        except:
            print('Registration failed due to issues resolving the registry server hostname')
            print('Your peers will need to add you manually.')

        registerMessage = messageToJson(constructBasicMessage(RegistryMessageType.REGISTER_PEER))
        senderSocket = buildSenderSocket()

        #TODO MAKE SENDER SOCKET ACTUALLY CONNECT TO THE SERVER, RN ITS JUST AN UNCONNECTED SOCKET
        if sendToSingleAdr(registerMessage, senderSocket):
            print('Failed to register with registry server. Your peers will need to add you manually.')
    initialisationComplete.set()


#************************************************************
#helper, constructs socket for establishing initial connection to another peer
def buildSenderSocket():
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    senderSocket.bind((env['CLIENT_LISTEN_IP'], 0)) #bind to specific sender adr so we can receive replies
    senderSocket.settimeout(0.25)
    return senderSocket


#************************************************************
#helper, sends a single message to all peers
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


#************************************************************
#helper, used to update peer list and network info when a peer's connection fails
#if peers fall to 0, triggers the display of a warning message
def handlePeerFailure(peer, peers):
    with peersLock:
        connection = networkEntries[peer]['connection']
        del networkEntries[peer]
        peers.remove(peer)
        selector.unregister(connection)
        silentFailureClose(connection)
        remainingPeers = len(peers)
        updateLivePeerCountGUI(remainingPeers)

        #If there was some point in time where we were not connected to any peers
        #we might have missed a message, so all messages that were causally linked to that message
        #can never be delivered. Flag to the user that we may be in that state, so they can make the
        #decision to restart or not.
        #
        #In a real application, it would make sense to shut the app completely
        #but as this is a demo, it's better to show we are able to detect this type of failure
        if remainingPeers == 0:
            statusUpdateGUI('NEW MESSAGES MAY NOT HAVE BEEN RECEIVED', True)


#************************************************************
#helper for updating peer list and network info when a connection fails
#if the number of connected peers falls to 0, triggers the display of a warning message
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


#************************************************************
#helper, enqueues the node's initial HELLO message
def sayHello(peers, outgoingMessageQueue):
    helloMessage = messageToJson(constructHello(processId))
    outgoingMessageQueue.put(helloMessage)
    registerAndCompleteInitialisation() #TODO - STOP INITIALISATION UNTIL HELLO COMPLETES

def main():

    #messages that have been read from a socket and need to be handled
    #hasAlreadyBeenHeldBack element is only used for simulating network delay
    #[(networkEntry, message, hasAlreadyBeenHeldBack)]
    messagesToHandle = Queue()

    #messages that need to be broadcast
    #[(message, isRetransmitting)]
    outgoingMessageQueue = Queue()

    #connections
    connectionQueue = Queue()
    
    #use with 'messageLock' to ensure mutex
    receivedMessages = {}

    #room for extension - add new peers at runtime based on received messages, so network is more fault tolerant
    #not added for this project, as this is just a demonstration of our vector clocks and causal delivery

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
        if sendToSingleAdr(getPeerMessage, senderSocket):
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
        unconnectedPeers = peerData['peers']
        print('Received peers from registry: ', unconnectedPeers)
        if (len(unconnectedPeers) == 0):
            print('Registry had no peers, registering self')
            registerAndCompleteInitialisation()
    else:
        unconnectedPeers = getPeerHosts()
    
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
            print('Could not establish connection for peer {0}'.format(peer))
            print('Proceeding without it')

    if len(peers) == 0:
        print('STARTED WITH NO PEERS')
        initiallyUnconnected.set()
    
    #create worker threads
    broadcastWorkers = []
    handlerWorkers = []
    readWorkers = []
    for i in range(int(env['CLIENT_WORKER_THREADS'])):
        broadcastWorkers.append(Thread(target=broadcastWorker, args=(outgoingMessageQueue, receivedMessages, peers, processId)))
        handlerWorkers.append(Thread(target=handlerWorker, args=(messagesToHandle, receivedMessages, outgoingMessageQueue, )))
        readWorkers.append(Thread(target=readWorker, args=(messagesToHandle, peers, )))
    for i in range(int(env['CLIENT_WORKER_THREADS'])):
        broadcastWorkers[i].start()
        handlerWorkers[i].start()
        readWorkers[i].start()

    #setup listener
    #for now, only use ipv4 - can swap to V6 fairly easily later if we want to
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((env['CLIENT_LISTEN_IP'], int(env['PROTOCOL_PORT'])))
    acceptSocket.listen()
    print('Client listening at {0} on port {1}'.format(env['CLIENT_LISTEN_IP'], env['PROTOCOL_PORT']))
    print("Process ID is", processId)
    acceptThread = Thread(target=acceptWorker, args=(acceptSocket, peers))
    acceptThread.start()


    #clone state of some other node in the network as own initial state
    if len(peers) > 0:
        sayHello(peers, outgoingMessageQueue)
        print('connecting to the network, please wait...')
    else:
        print('waiting for at least one other peer to establish connection...')

    #don't start the GUI until hello completes
    while not initialisationComplete.is_set():
        time.sleep(0.1)

    #start GUI from template file
    Builder.load_file('layout.kv')
    GUI(title='CHAT CLIENT [{0}]'.format(env['CLIENT_LISTEN_IP'])).run()

    print('GUI closed, terminating threads...')
    shutdownFlag.set()
    for worker in broadcastWorkers:
        worker.join()
    print('joined broadcasters...')
    for worker in readWorkers:
        worker.join()
    print('joined readers...')
    for worker in handlerWorkers:
        worker.join()
    print('joined handlers...')
    acceptThread.join()
    silentFailureClose(acceptSocket)
    print('all threads closed... exiting...')
    


#************************************************************
#setup env

env = loadArgsAndEnvClient(sys.argv)
print('Combined env and argv config:', dict(env))

#************************************************************
#state

#maps a peer --> object containing peer socket, socket lock, current message size, read buffer
networkEntries = {}

#initial message collector, stores edge case messages that arrive before HELLO_RESPONSE arrives
preInitialisedReceivedMessages = [] #use with 'preInitialisedLock' to ensure mutex

#read socket selector
selector = selectors.DefaultSelector()

#************************************************************
#locks

#p2p state locks
peersLock = Lock() #lock for peers list
messageLock = Lock() #lock for received message dict
preInitialisedLock = Lock() #lock for pre-initialisation message queue

#vector clock locks
deliverabilityLock = Lock() #lock for checking for message deliverability
incrementLock = Lock() #lock for this peer to increment its own vector clock

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

processId = env['CLIENT_LISTEN_IP']
# This process's vector clock - initialised with its own ip i.e 
# [ [127.0.0.XX, 0] ]
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