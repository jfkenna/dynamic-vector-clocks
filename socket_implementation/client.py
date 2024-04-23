from threading import Thread
from queue import Queue
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor
from shared.message import constructJsonMessage, parseJsonMessage, MessageType
import socket

#doesn't really need to be a function, just here in case we want to
#move some lifecycle stuff here later
def acceptWorker(taskQueue, serverSocket):
    print('[a0] Started')
    while True:
        taskQueue.put(serverSocket.accept())
        print('[a0] Accepted connection')


def networkWorker(taskQueue, receivedMessages, peers, id):
    print('[w{0}] Started'.format(id))
    while True:
        connection, adr = taskQueue.get()
        #TODO properly read multiple datagrams until seperator is reached
        #for now, just assume total message size will be < 1024
        data = connection.recv(1024)
        message = parseJsonMessage(data)
        print('[w{0}] Recieved message {1}'.format(id, message))
        if message == None:
            print('[w{0}] Parse error')
            continue
        handleMessage(message)


def handleMessage(message, receivedMessages):
    #guard against re-handling already received messages
    if message['clock'] in receivedMessages:
        return
    #add to list of received messages
    receivedMessages[message['clock']] = True

    #TODO processing / handling (and causal delivery)

def validateEnv(env):

    for required in ['CLIENT_LISTEN_PORT', 'CLIENT_LISTEN_IP', 'CLIENT_WORKER_THREADS']:
        if required not in env:
            print(required + ' not specified')
            return False

    #TODO add more detailed validation (e.g. port in range [1, 65353])
    return True

def getPeerHosts():
    initialPeers = []
    print("Enter peer IPs/hostnames [enter \'finished\' to continue]")
    while True:
        peer = input('Enter hostname: ')
        if peer == 'finished':
            if (len(initialPeers) == 0):
                print('You must provide at least one peer to continue')
                continue
            return initialPeers
        try:
            resolvedAdr = socket.gethostbyname(peer)
            initialPeers.append(resolvedAdr)
            print('Added peer at {0}'.format(resolvedAdr))
        except socket.error:
            print('Couldn\'t resolve hostname, enter a different value')
            continue

def main():

    #parse and validate .env
    env = dotenv_values('.env')
    print('Client env config:', dict(env))

    if not validateEnv(env):
        print('.env failed validation, exiting...')
        return


    #create shared resources
    #suprisingly, default python queue is thread-safe
    taskQueue = Queue()
    receivedMessages = {} #TODO check if this is thread safe

    #TODO consider passing information about new peers at runtime, so network is more fault tolerant
    #this is an extension, so for our first implementation just start with a fixed set of peers that we can multicast to
    peers = getPeerHosts()
    
    #setup listener
    acceptSocket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM) #ipv6 w/ TCP channel
    acceptSocket.bind((env['CLIENT_LISTEN_IP'], int(env['CLIENT_LISTEN_PORT'])))
    acceptSocket.listen()
    print('Client listening at {0} on port {1}'.format(env['CLIENT_LISTEN_IP'], env['CLIENT_LISTEN_PORT']))
    acceptThread = Thread(target=acceptWorker, args=(taskQueue, acceptSocket, ))
    acceptThread.start()

    #worker threads
    workerThreads = []
    for i in range(0, int(env['CLIENT_WORKER_THREADS'])):
        worker = Thread(target=networkWorker, args=(taskQueue, receivedMessages, peers, i))
        worker.start()

    acceptThread.join()
    workerThreads.join()


main()