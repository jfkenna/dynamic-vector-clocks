def prependContentLengthHeader(encodedMessage):
    contentLength = len(encodedMessage)
    #append fixed-width standardized long to start of message
    fixedWidthHeader = struct.pack('!li', contentLength)
    return fixedWidthHeader + encodedMessage

def sendWithHeaderAndEncoding(connection, message):
    encoded = message.encode('utf-8')
    witHHeader = prependContentLengthHeader(encoded)
    return connection.send(witHHeader)

#we assume that each connection is opened, sends a single message, and is then closed
#in such a system, there is no need to read until a terminator - simply wait for connection to close or message length to be read
def readSingleMessage(connection):
    headerSize = struct.calcsize('!li')
    contentLength = None
    received = ''
    while True:
        data = connection.recv(4000)

        #return early if socket closed early
        if not data:
            return None
        
        received = received + data
        
        #extract message length if not already set
        if contentLength == None and len(received) >= headerSize:
            contentLength = struct.unpack('!li', received[:headerSize])
            received = received[headerSize:]
        
        #return once entire message read
        if len(received) >= contentLength:
            return received