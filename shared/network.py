import struct
import socket
from threading import Lock


#All messages sent by the system follow the following format:

#|SIZE                           |TYPE                                |DESCRIPTION
#|4 bytes (platform independent) |Fixed width big-endian encoded long |Represents length of message content in bytes
#|variable length                |utf-8 encoded byte string           |Message content


#************************************************************
#message helpers

#attaches a fixed width size header to start of message 
def prependContentLengthHeader(encodedMessage):
    contentLength = len(encodedMessage)
    #preprend fixed-width standardized long to message
    fixedWidthHeader = struct.pack('!l', contentLength)
    return fixedWidthHeader + encodedMessage


#encodes message using utf-8, then attaches header
def sendWithHeaderAndEncoding(connection, message):
    encoded = message.encode('utf-8')
    withHeader = prependContentLengthHeader(encoded)
    return connection.send(withHeader)



#************************************************************
#network IO helpers

#reads a fixed block of data from a peer's connection and adds any complete messages to the message queue
#not guaranteed to read a complete message - may need multiple invocations to build up the full message
#returns True if an error occurred during the read attempt, False otherwise
def continueRead(networkEntry, messageQueue):
    headerSize = struct.calcsize('!l')

    try:
        data = networkEntry['connection'].recv(2048)
    except socket.error as err:

        #nothing in socket currently available to read (nonblocking socket)
        #return False, as not a true failure
        if (err.errno == 11):
            return False
        else:
            #all other error codes indicate a genuine error must have occurred
            print('[ERR] Error reading from', networkEntry['connection'], err)
            return True

    if not data or len(data) == 0:
        return True
    
    networkEntry['buffer'] += data
    
    #handle complete messages until no FULLY COMPLETE messages remain
    #partial messages may still be in the buffer
    while True:
        if networkEntry['contentLength'] == None:
            #if we have read enough data to know the message length, extract it
            if len(networkEntry['buffer']) >= headerSize:
                networkEntry['contentLength'] = struct.unpack('!l', networkEntry['buffer'][:headerSize])[0]
                networkEntry['buffer'] = networkEntry['buffer'][headerSize:]
            #if haven't received enough data to know the message length, return
            else:
                return False

        #read complete message and remove it from the buffer if possible
        if networkEntry['contentLength'] != None and (len(networkEntry['buffer']) >= networkEntry['contentLength']):
            message = networkEntry['buffer'][:networkEntry['contentLength']]
            networkEntry['buffer'] = networkEntry['buffer'][networkEntry['contentLength']:]
            networkEntry['contentLength'] = None

            #associate message with sender
            messageWithPeer = (networkEntry, message, False)
            messageQueue.put(messageWithPeer)

        #if no complete messages are present, return
        else:
            return False


#read helper used for communication with registry server
#reads from a socket until a single message is consumed, then returns the message
#returns the consumed message, or None if the connection closed
#NOTE: UNSAFE TO USE IF MULTIPLE MESSAGES ARE BEING SENT THROUGH THE SOCKET
def readSingleMessage(connection):
    headerSize = struct.calcsize('!l')
    contentLength = None
    received = b''
    while True:
        data = connection.recv(2048)

        #return if socket closed early
        if not data:
            return None
        
        received = received + data
        
        #extract message length if not already set
        if contentLength == None and len(received) >= headerSize:
            contentLength = struct.unpack('!l', received[:headerSize])[0]
            received = received[headerSize:]
        
        #return message once full length has been read
        #any 'overreads' will be lost
        if len(received) >= contentLength:
            return received[:contentLength]


#helper for sending a single message to a single socket
#returns True if the send failed, False otherwise
def sendToSingleAdr(message, connectedSocket):
    try:
        sendWithHeaderAndEncoding(connectedSocket, message)
    except socket.error:
        print('Error sending message to peer: {0}'.format(socket.error))
        return True
    return False


#helper for closing connections
#suppresses error messages from double-closes
def silentFailureClose(connection):
    try:
        connection.close()
    except:
        pass


#builds dictionary representing a p2p network connection. Contains:
#a socket and its associated lock
#the current data that has been read from the socket
#the header-indicated length of the current message
def buildNetworkEntry(connection):
    return {
        'connection': connection,
        'contentLength': None,
        'buffer': b'',
        'lock': Lock()
    }
        
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
