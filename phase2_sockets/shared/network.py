import struct
import socket

#All messages sent by the system follow the following format:
#Each connection only sends a single message before closing, so there is no need to define separators

#|SIZE                           |TYPE                                |DESCRIPTION
#|4 bytes (platform independent) |Fixed width big-endian encoded long |Represents length of message content in bytes
#|variable length                |utf-8 encoded byte string           |Message content


def prependContentLengthHeader(encodedMessage):
    contentLength = len(encodedMessage)
    #append fixed-width standardized long to start of message
    fixedWidthHeader = struct.pack('!l', contentLength)
    return fixedWidthHeader + encodedMessage

def sendWithHeaderAndEncoding(connection, message):
    encoded = message.encode('utf-8')
    withHeader = prependContentLengthHeader(encoded)
    return connection.send(withHeader)

#we assume that each connection is opened, sends a single message, and is then closed
#in such a system, there is no need to read until a terminator - simply wait for connection to close or message length to be read
def readSingleMessage(connection):
    headerSize = struct.calcsize('!l')
    contentLength = None
    received = b''
    while True:
        data = connection.recv(2048)

        #return early if socket closed early
        if not data:
            return None
        
        received = received + data
        
        #extract message length if not already set
        if contentLength == None and len(received) >= headerSize:
            contentLength = struct.unpack('!l', received[:headerSize])[0]
            received = received[headerSize:]
        
        #return once entire message read
        if len(received) >= contentLength:
            return received

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

def silentFailureClose(connection):
    try:
        connection.close()
    except:
        pass