from threading import Thread, Lock, Event
from queue import Queue
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor
from shared.validator import validateEnv
from shared.client_message import constructMessage, constructHello, constructHelloResponse, parseJsonMessage, messageToJson, MessageType
from shared.server_message import RegistryMessageType, constructBasicMessage
from shared.vector_clock import canDeliver, deliverMessage, handleMessageQueue, incrementVectorClock
from shared.network import sendWithHeaderAndEncoding, continueRead, silentFailureClose, sendToSingleAdr
from GUI_components import GUI, textUpdateGUI, statusUpdateGUI, clearStatusGUI
from kivy.lang import Builder
from kivy.app import App
import socket
import uuid
import sys
import time
import selectors

def acceptWorker(serverSocket, messagesToHandle):

    print('[a0] Started')
    while True:
        print(shutdownFlag.is_set())
        if shutdownFlag.is_set():
            return
        
        #TODO double check that network entry is always ready by the time messages are received
        newConnection = serverSocket.accept()
        newConnection.setblocking(False)
        selector.register(newConnection, selectors.EVENT_READ, lambda readable: readCallback(readable, messagesToHandle))

        with peersLock:
            networkEntries[peer] = buildNetworkEntry(newConnection)
            peers.append(peer)


def readCallback(readableSocket, messagesToHandle):
    peer = readableSocket.getpeername()[0] #TODO ERROR HANDLING FOR CASE WHERE SOCKET CLOSES

    #skip dead entries TODO check if actually necessary
    networkEntry = networkEntries.get(peer, None)
    if networkEntry == None:
        return

    #read available messages, then 
    continueRead(networkEntry, messagesToHandle)
    select.register(readableSocket, selectors.EVENT_READ, readCallback)


def broadcastWorker(outgoingMessageQueue, peers, processId):
    global processVectorClock 
    print('[s0] Started')

    #pass in queue once GUI is ready for binding
    while True:
        if App.get_running_app():
            App.get_running_app().setQueue(outgoingMessageQueue)
            break
        time.sleep(0.005)
    
    #once UI is setup, begin handling broadcasts
    while True:
        if shutdownFlag.is_set():
            return
        receivedMessage = outgoingMessageQueue.get()

        #if message originates from UI, hydrate with local clock
        #otherwise, retransmit without changes
        if len(receivedMessage['clock'].keys()):
            with incrementLock:
                processVectorClock = incrementVectorClock(processVectorClock, processId)
                outgoingMessage = messageToJson(constructMessage(MessageType.BROADCAST_MESSAGE, processVectorClock, receivedMessage['text'], processId))
        else:
            outgoingMessage = receivedMessage
        broadcastToPeers(outgoingMessage, peers)


def handlerWorker(messagesToHandle, outgoingMessageQueue):
    while True:
        #TODO can put a timeout here, then check if flag for exit is set
        messageInfo = messagesToHandle.get()

        message = parseJsonMessage(messageInfo[1], [], True)
        #do nothing if connection crashes at some stage before message is handled
        peerNetworkData = networkEntries.get(messageInfo[0], None)
        if peerNetworkData == None:
            continue

        if message['type'] == MessageType.HELLO:
            handleHello(peerNetworkData, message)
        if message['type'] == MessageType.HELLO_RESPONSE:
            handleHelloResponse(peerNetworkData, message)
        if message['type'] == MessageType.BROADCAST_MESSAGE:
            handleBroadcastMessage(message, receivedMessages, outgoingMessageQueue)
        if message == None:
            print('[w{0}] Parse error'.format(id))
            continue

def handleHello(networkEntry, message):
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
        #don't initialise if peer couldn't receive message
        if sendToSingleAdr(emptyHelloResponse, networkEntry['connection']):
            #TODO handle peer failure
            print('Failed to send clone data to peer. Remaining unitialised')
            return
        silentFailureClose(senderSocket)
        
        #initialise after sending peer data
        handleMessageQueue(processVectorClock, preInitialisedReceivedMessages, None) #TODO double check if necessary for this empty case
        registerAndCompleteInitialisation()
        return

    #TODO need to lock on vector clock and message queue here
    #i think i'll just make a monitor class to simplify all these locks
    #for now, don't even lock, just so basic functionality is present
    helloResponse = messageToJson(constructHelloResponse(processId, processVectorClock, processMessageQueue))
    if sendToSingleAdr(helloResponse, networkEntry['connection']):
        #TODO handle peer failure
        print('Failed to send clone data to peer')
        return

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
    

def handleBroadcastMessage(message, receivedMessages, outgoingMessageQueue):
    global processVectorClock
    global processMessageQueue

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

    # If this processId is the sender of the message
    if not message['sender'] == processId:
        with deliverabilityLock:
            if canDeliver(processVectorClock, message):
                processVectorClock = deliverMessage(processVectorClock, message, processId)
                textUpdateGUI(message['sender'], message['text'])
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

        #TODO MAKE SENDER SOCKET ACTUALLY CONNECT TO THE SERVER, RN ITS JUST AN UNCONNECTED SOCKET
        if sendToSingleAdr(registerMessage, senderSocket):
            print('Failed to register with registry server. Your peers will need to add you manually.')
    initialisationComplete.set()


def buildSenderSocket():
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    senderSocket.bind((env['CLIENT_LISTEN_IP'], 0)) #bind to specific sender adr so we can receive replies
    senderSocket.settimeout(0.25) #250 ms maximum timeout - allows reasonable amounts of network delay
    return senderSocket


def broadcastToPeers(message, peers):
    for peer in peers:
        peerConnection = networkEntries[peer]['connection']
        if sendToSingleAdr(message, peerConnection):
            handlePeerFailure(peer)
    else:
        clearStatusGUI()


def handlePeerFailure(peer):
    with peersLock:
        del networkEntries[peer]
        peers.remove(peer)

        #handle total failure case
        #TOOD exit system
        if len(peers) == 0:
            print('Totally disconnected from network')
    return

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

    #TODO check if any peers are alive
    registerAndCompleteInitialisation()

def main():

    #connections in the system. peer -> (socket, socket lock, current message size, read bytes buffer)
    networkEntries = {}

    #messages that have been read from a socket and need to be handled
    #[(peer, message)]
    messagesToHandle = Queue()

    #messages that need to be broadcast
    #[(message, isRetransmitting)]
    outgoingMessageQueue = Queue()

    #connections
    connectionQueue = Queue()
    
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
            connection = p2pSocket.connect((peer, int(env['PROTOCOL_PORT'])))
            networkEntries[peer] = buildNetworkEntry()
            peers.append(peer)
        except socket.error:
            print('Could not establish connection for peer {0}'.format(peer))
            print('Proceeding without it')

    if len(peers) == 0:
        print('STARTED WITH NO PEERS')
        initiallyUnconnected.set()
    
    #create worker threads
    broadcastWorkers = []
    handlerWorkers = []
    for i in range(int(env['CLIENT_WORKER_THREADS'])):
        broadcastWorkers.append(Thread(target=broadcastWorker, args=(outgoingMessageQueue, peers, processId)))
        handlerWorkers.append(Thread(target=handlerWorker, args=(messagesToHandle, outgoingMessageQueue)))
    for i in range(int(env['CLIENT_WORKER_THREADS'])):
        broadcastWorkers[i].start()
        handlerWorkers[i].start()

    #setup listener
    #for now, only use ipv4 - can swap to V6 fairly easily later if we want to
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((env['CLIENT_LISTEN_IP'], int(env['PROTOCOL_PORT'])))
    acceptSocket.listen()
    print('Client listening at {0} on port {1}'.format(env['CLIENT_LISTEN_IP'], env['PROTOCOL_PORT']))
    print("Process ID is", processId)
    acceptThread = Thread(target=acceptWorker, args=(acceptSocket, messagesToHandle))
    acceptThread.start()


    #clone state of some other node in the network as own initial state
    if len(peers) > 0:
        sayHello(peers)
        print('connecting to the network, please wait...')
    else:
        print('waiting for at least one other peer to establish connection...')

    #don't start the GUI until hello completes
    while not initialisationComplete.is_set():
        time.sleep(0.1)

    #start GUI from template file
    Builder.load_file('layout.kv')
    GUI(title='CHAT CLIENT [{0}]'.format(env['CLIENT_LISTEN_IP'])).run()

    #set exit flag once GUI terminates
    #TODO get this actually working, right now it fails due to threads blocking (python has no thread interrupt method)
    shutdownFlag.set()
    acceptSocket.close()


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

#selector over sockets
selectors.DefaultSelector() 

#shutdown event
shutdownFlag = Event()

#global lock for received message dict
messageLock = Lock()

#global lock for pre-initialisation message queue
preInitialisedLock = Lock()

#global lock for checking for message deliverability
deliverabilityLock = Lock()

#global lock for this peer to increment its own vector clock
incrementLock = Lock()

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