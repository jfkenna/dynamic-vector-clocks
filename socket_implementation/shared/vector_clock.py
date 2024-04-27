def incrementVectorClock(processVectorClock, processId):
    revisedVectorClock = processVectorClock
    for clock in processVectorClock:
        if clock[0] == processId:  # Obtain this process's clock within the vector clock (first index)
            clock[1] += 1           # Increment by 1
            break                   # Exit the loop
    return revisedVectorClock

def mergeClocks(messageVectorClock, processVectorClock):
    print("merging")
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