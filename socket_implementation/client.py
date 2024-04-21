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


def networkWorker(taskQueue, id):
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


def handleMessage(message):
    #TODO logic for updating clock, displaying messages etc.
    return

def validateEnv(env):

    for required in ['CLIENT_LISTEN_PORT', 'CLIENT_LISTEN_IP', 'CLIENT_WORKER_THREADS']:
        if required not in env:
            print(required + ' not specified')
            return False

    #TODO add more detailed validation (e.g. port in range [1, 65353])
    return True

def main():

    #parse and validate .env
    env = dotenv_values('.env')
    print('Client env config:', dict(env))

    if not validateEnv(env):
        print('.env failed validation, exiting...')
        return


    #suprisingly, default python queue is thread-safe
    taskQueue = Queue()

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
        worker = Thread(target=networkWorker, args=(taskQueue, i))
        worker.start()

    acceptThread.join()
    workerThreads.join()


main()