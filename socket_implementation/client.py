import socket
from threading import Thread
from queue import Queue
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor

#doesn't really need to be a function, just here in case we want to
#move some lifecycle stuff here later
def acceptWorker(taskQueue, serverSocket):
    print('Started accept worker')
    while True:
        taskQueue.put(serverSocket.accept())


def networkWorker(taskQueue):
    print('Started network worker')
    while True:
        connection = taskQueue.get()
        
        #TODO read from connection
        message = 'TODO'
        handleMessage(message)


def handleMessage(message):
    #TODO
    print("updating vector clock...")
    print("updating message display")

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
    #if we start getting issues, we can swap to a standard thread pool
    #sometimes the executor can hide exceptions / warnings
    with ThreadPoolExecutor(max_workers=int(env['CLIENT_WORKER_THREADS'])) as executor:
        executor.map(networkWorker, [taskQueue for i in range(0, int(env['CLIENT_WORKER_THREADS']))])

    acceptThread.join()


main()