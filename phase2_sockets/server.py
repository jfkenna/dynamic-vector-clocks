import socket
import uuid
import sys
from threading import Thread, Lock
from queue import Queue
from dotenv import dotenv_values
from shared.validator import validateEnv
from shared.server_message import RegistryMessageType, constructBasicMessage, constructPeerResponseMessage
from shared.client_message import parseJsonMessage, messageToJson
from shared.network import sendWithHeaderAndEncoding, readSingleMessage

def silentFailureClose(connection):
    try:
        connection.close()
    except:
        pass

def acceptWorker(connectionQueue, serverSocket):
    while True:
        connectionQueue.put(serverSocket.accept())

def handleMessage(message, connection, peers):
    match message['type']:
        case RegistryMessageType.GET_PEERS:
            with lock:
                response = messageToJson(constructPeerResponseMessage(list(peers.keys())))
            sendWithHeaderAndEncoding(connection, response)

        case RegistryMessageType.REGISTER_PEER:
            peerKey = connection.getpeername()[0]
            with lock:
                peers[peerKey] = True
            response = messageToJson(constructBasicMessage(RegistryMessageType.OK))
            sendWithHeaderAndEncoding(connection, response)

        case RegistryMessageType.DEREGISTER_PEER:
            peerKey = connection.getpeername()[0]
            with lock:
                if peerKey in peers:
                    del peers[peerKey]
            response = messageToJson(constructBasicMessage(RegistryMessageType.OK))
            sendWithHeaderAndEncoding(connection, response)

        case _:
            response = messageToJson(constructBasicMessage(RegistryMessageType.BAD_MESSAGE))
            sendWithHeaderAndEncoding(connection, response)
    print('After operation {0}'.format(peers))
    return

def worker(connectionQueue, peers):
    while True:
        connection, adr = connectionQueue.get()
        try:
            data = readSingleMessage(connection)
        except socket.error:
            print('Error reading incoming message')
            silentFailureClose(connection)
            continue

        parsedMessage = parseJsonMessage(data, ['id', 'type'])
        if parsedMessage == None:
            response = messageToJson(constructBasicMessage(RegistryMessageType.BAD_MESSAGE))
            silentFailureClose(connection)
            continue

        try:
            handleMessage(parsedMessage, connection, peers)
        except socket.error:
            print('Error handling message: {0}'.format(socket.error))
        silentFailureClose(connection)
        continue


def main():
    #shared data
    connectionQueue = Queue()
    peers = {}
    
    #initial setup copied from client
    acceptSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    acceptSocket.bind((ip, int(env['REGISTRY_PROTOCOL_PORT'])))
    acceptSocket.listen()
    print('Server listening at {0} on port {1}'.format(ip, env['REGISTRY_PROTOCOL_PORT']))
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
if validateEnv(env, ['REGISTRY_PROTOCOL_PORT']) == None:
    exit()
ip = sys.argv[1]
lock = Lock()
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
[8] New York University. "Non-blocking Communication". GitHub Pages. https://nyu-cds.github.io/python-mpi/03-nonblocking/#:~:text=In%20MPI%2C%20non%2Dblocking%20communication,uniquely%20identifys%20the%20started%20operation. (accessed Mar. 24, 2024).
[9] L. Dalcin. "mpi4py.MPI.Message". MPI for Python. https://mpi4py.readthedocs.io/en/stable/reference/mpi4py.MPI.Message.html (accessed Mar. 30, 2024).
[10] W3Schools. "Python String split() Method". W3Schools. https://www.w3schools.com/python/ref_string_split.asp (accessed Mar. 30, 2024).
[11] C. Kolade. "Python Switch Statement - Switch Case Example". freeCodeCamp. https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ (accessed Mar. 30, 2024).
[12] spiderman. "How to find string that start with one letter then numbers". FME Community. https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 (accessed Mar. 30, 2024).
[13] TutorialsTeacher. "Grouping in Regex". TutorialsTeacher. https://www.tutorialsteacher.com/regex/grouping (accessed Mar. 30, 2024).
[14] hoju. "Extract part of a regex match". Stack Overflow. https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match (accessed Mar. 30, 2024).
[15] M. Breuss. "How to Check if a Python String Contains a Substring". Real Python. https://realpython.com/python-string-contains-substring/ (accessed Mar. 30, 2024).
[16] Python Principles. "How to convert a string to int in Python". Python Principles. https://pythonprinciples.com/blog/python-convert-string-to-int/#:~:text=To%20convert%20a%20string%20to%20an%20integer%2C%20use%20the%20built,an%20integer%20as%20its%20output. (accessed Mar. 30, 2024).
[17] TransparenTech LLC. "Generate a UUID in Python". UUID Generator. https://www.uuidgenerator.net/dev-corner/python (accessed Mar. 30, 2024).
[18] W3Schools. "Python - List Comprehension". W3Schools. https://www.w3schools.com/python/python_lists_comprehension.asp (accessed Mar. 30, 2024).
[19] greye. "Get loop count inside a for-loop [duplicate]". Stack Overflow. https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop (accessed Mar. 30, 2024).
[20] G. Ramuglia. "Using Bash to Count Lines in a File: A File Handling Tutorial". I/O Flood. https://ioflood.com/blog/bash-count-lines/#:~:text=To%20count%20lines%20in%20a%20file%20using%20Bash%2C%20you%20can,number%20of%20lines%20it%20contains.&text=In%20this%20example%2C%20we%20use,on%20a%20file%20named%20'filename. (accessed Mar. 30, 2024).
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