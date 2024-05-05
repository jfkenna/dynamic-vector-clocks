def incrementVectorClock(processVectorClock, processId):
    revisedVectorClock = processVectorClock
    for clock in processVectorClock:
        if clock[0] == processId:  # Obtain this process's clock within the vector clock (first index)
            clock[1] += 1           # Increment by 1
            break                   # Exit the loop
    return revisedVectorClock

def mergeClocks(processVectorClock, messageVectorClock): 
    # Create a new process DVC that will mutate based on what it has seen before, or append with the ones it hasn't seen
    newProcessVectorClock = processVectorClock
    # For each row in the message DVC
    for row_m in messageVectorClock:
        seen_row_m = False                          # Seen message row boolean
        for row_p in newProcessVectorClock:         # For each row in the process DVC
            if row_m[0] == row_p[0]:                # If the message's row is a index that the receiver process has seen
                row_p[1] = max(row_m[1], row_p[1])  # Update row_p in new_process_dvc with max(msg, p)
                seen_row_m = True                   # The process has seen it now, break off
                break
        if not seen_row_m:                          # If the message DVC's row is new to the receiver
            newProcessVectorClock.append(row_m)     # Add this row to new_process_dvc
    return newProcessVectorClock

def seenSender(processVectorClock, senderUuid):
    seenSender = False
    for row_p in processVectorClock:            # Seen message row boolean
        if row_p[0] == senderUuid:              # If the message's row is a index that the receiver process has seen
            seenSender = True                   # The process has seen it now, break off
            break
    return seenSender

def obtainIndexOfUuid(clock, uuid):
    index = 0
    for idx in range(len(clock)):
        if clock[idx][0] == uuid:
            index = idx
            break
    return index

def deliverMessage(processVectorClock, message, processId, uiUpdater):
    # Print out the message
    senderName = 'You' if (message['sender'] == processId) else message['sender']
    print('[{0}]: {1}'.format(senderName, message['text']))
    uiUpdater(message['sender'], message['text'])

    # Merge VCs upon delivery
    messageVectorClock = message['clock']
    newProcessVectorClock = mergeClocks(processVectorClock, messageVectorClock)
    return newProcessVectorClock

def canDeliver(processVectorClock, message):

    print("My clock {0}, Message clock {1}".format(processVectorClock, message))

    delivarable = False
    # Variable setup
    messageVectorClock = message["clock"]                       # Message DVC
    senderUuid = message["sender"]                              # Sender UUID



    hasSeenSender = seenSender(processVectorClock, senderUuid)
    mVectorClockSenderIdx = obtainIndexOfUuid(messageVectorClock, senderUuid)
    
    if hasSeenSender:
        # Lets obtain the index of the sender in the process and message VCs
        pVectorClockSenderIdx = obtainIndexOfUuid(processVectorClock, senderUuid)
        # Check if the message's sender index in the message VC is 1 greater than the index in the process's DVC
        senderIndexValid = messageVectorClock[mVectorClockSenderIdx][1] == processVectorClock[pVectorClockSenderIdx][1] + 1 
    else:
        #if haven't seen sender, message must be their first
        senderIndexValid = messageVectorClock[mVectorClockSenderIdx][1] == 1

    # Check other indexes on the message clock are <= the process's clock
    otherIndexesValid = True                                # Initially, set other_msg_index_valid True (all other known index DC)
    for row in messageVectorClock:                          # For each known process in the message clock
        if not row[0] == senderUuid:     
            pVectorClockOtherUIdx = obtainIndexOfUuid(processVectorClock, row[0])        # Find the row of the other UUID in the process's VC
            if not row[1] <= processVectorClock[pVectorClockOtherUIdx][1]:
                otherIndexesValid = False
                break

    # Set deliverable upon the sender index valid (message > by 1) and each other index in the message VC is <= process's index
    delivarable = senderIndexValid and otherIndexesValid  

    return delivarable

def handleMessageQueue(processVectorClock, queue, message, uiUpdater):
    currentVectorClock = processVectorClock
    firstPass = True
    iterator = 0

    # Iterate over until we can't deliver any messages/nothing in the queue
    while True:
        if len(queue) >= 1:
            if iterator == len(queue): break                                # Break - queue is exhausted
            elif queue[iterator] == message and firstPass: iterator += 1    # Iterate to next message in the queue
            else:
                queuedMessage = queue[iterator]                             # Grab the next message
                if canDeliver(currentVectorClock, queuedMessage):           # Can the message be delivered?
                    currentVectorClock = deliverMessage(currentVectorClock, queuedMessage, message['sender'], uiUpdater)     # Deliver the message if it can be delivered
                    queue.pop(iterator)                                     # Pop the message from the queue
                    iterator = 0                                            # Reset iterator to 0
                    firstPass = False                                       # Not the first pass anymore
                else:                                                       # If the the message can't be delivered?
                    iterator += 1                                           # Move to the next iteration
        else: break
    return currentVectorClock

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