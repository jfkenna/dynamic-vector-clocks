def incrementVectorClock(processVectorClock, processId):
    revisedVectorClock = processVectorClock
    for clock in processVectorClock:
        if clock[0] == processId:  # Obtain this process's clock within the vector clock (first index)
            clock[1] += 1           # Increment by 1
            break                   # Exit the loop
    return revisedVectorClock