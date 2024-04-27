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

def deliverMessage(processVectorClock, message):
    messageVectorClock = message['clock']
    newProcessVectorClock = mergeClocks(processVectorClock, messageVectorClock)
    return newProcessVectorClock

def canDeliver(processVectorClock, message):
    delivarable = False
    # Variable setup
    messageVectorClock = message["clock"]                       # Message DVC
    senderUuid = message["sender"]                              # Sender UUID

    print("Process's VC:,", processVectorClock)
    print("Message VC:", messageVectorClock)
    print("senders UUID", senderUuid)
    if seenSender(processVectorClock, senderUuid):
        print("seen")
        # Lets obtain the index of the sender in the process and message VCs
        pVectorClockSenderIdx = obtainIndexOfUuid(processVectorClock, senderUuid)
        mVectorClockSenderIdx = obtainIndexOfUuid(messageVectorClock, senderUuid)

        print("Sender has index {0} in the processes VC".format(pVectorClockSenderIdx))
        print("Sender has index {0} in the message VC".format(mVectorClockSenderIdx))

        # Check if the message's sender index in the message VC is 1 greater than the index in the process's DVC
        senderIndexValid = messageVectorClock[mVectorClockSenderIdx][1] == processVectorClock[pVectorClockSenderIdx][1] + 1 
        print("Sender index valid?:", senderIndexValid)

        # Check other indexes on the message clock are <= the process's clock
        otherIndexesValid = True                                # Initially, set other_msg_index_valid True (all other known index DC)
        for row in messageVectorClock:                          # For each known process in the message clock
            if not row[0] == senderUuid:     
                pVectorClockOtherUIdx = obtainIndexOfUuid(processVectorClock, row[0])        # Find the row of the other UUID in the process's VC
                if not row[1] <= processVectorClock[pVectorClockOtherUIdx][1]:
                    otherIndexesValid = False
                    break

        delivarable = senderIndexValid and otherIndexesValid  
        if delivarable: 
            print("This message satisfied the DVC causal deliverability condition. Delivering.")
        else:
            print("This message did not satisfy the DVC causal deliverability condition. Will be enqueued.")
    else:
        delivarable = True      # TODO: Only until we implement initial hello where process knows of all processes

    return delivarable 