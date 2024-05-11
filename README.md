# COMP90020 - Distributed Algorithms - Team Double-J

This repository holds the source files of the project of Team Double-J (James Sammut and Joel Kenna) for COMP90020: Distributed Algorithms - for Semetser 1, 2024.

The main topic that the team has picked for investigation is Logical Time - and in particular, the implementation of **Dynamic Vector Clocks**. Initially, **Matrix Clocks** were selected as the team's first choice of algorithm to implement; with the aim of providing both unicast and broadcast causal delivery for chatting with a group of peers. However, we ultimately decided to use **Dynamic Vector Clocks**, for three main reasons:

- Dynamic Vector Clocks can add new entries at runtime, while matrix clocks cannot - this is beneficial for chat apps, where users may want to join a chat midway through
- Dynamic Vector Clocks have significantly reduced space complexity and network load when compared to Matrix Clocks (n entries vs n^2 entries)
- We realised that the real-world applications of a chat application primarily orient around broadcasting messages between peers, rather than single peer to single peer communication, and noted that causal delivery for broadcasts is possible with both matrix and vector clocks - this meant that if we forced all messages to be broadcast only, we could gain all the benefits associated with the use of dynamic vector clocks.

The repository consists of two main directories - `phase1_mpi` and `phase2_sockets`. The first phase provides an initial implementation of causal delivery with DVCs in python using MPI. The second phase extends this original implementation and uses the logic designed in phase one to build a peer to peer networked chat application in python. Invocation instructions and descriptions of the two phases are provided below.

## Phase 1 - `phase1_mpi`

### Approach

The first phase of this project is implementing the Dynamic Vector Clock (DVC) Algorithm using **Message Passing Interface** - or MPI for short. 

This is achieved around the _known_ input of a distributed system's processes's and events; where said events are sent and received between these processes. Both Dynamic Vector Clock (`dynamic_vector_clocks.py`) and Matrix Clock (MC) (`/matrix_clock.py`) implementations have been developed in this phase - the logic for checking for causal delivery in each slightly different, but applied in a similar way; shared functionality exists in the `/shared` directory.

Example input files live in this phases' `/examples` directory - this containing subdirectories for each `/dynamic_vector_clocks` and `/matrix_clocks` with specific examples. Unicast/broadcast examples are inclusive for both - and are line-by-line seperated with the events that happen at each process. For example, the below file denotes a 3 process system where:
- Process 1 **broadcasts** message 1, and **receives** message 2 (from Process 2).
- Process 2 **receives** message 1 (from Process 1), and **broadcasts** message 2.
- Process 3 **receives** message 1 (from Process 1), then **receives** message 2 (from Process 2).

```
b1, r2
r1, b2
r1, r2
```

In these examples, broadcast messages are denoted by `b<integer>`, unicast messages by `s<integer>`, receive events by `r<integer>` and internal events with an alphabetical character. Important to note is that for send event targeting on the receiving process end, the same integer must be used (i.e `s1` for the sender, `r1` for the receiver).

### Implementation

The process of Phase 1 and both these implementations are as follows:
1. Either `dynamic_vc.sh` or `matrix_clock.sh` are called from within their respective directories with Phase 1's invocation file to utilise. For example, `./phase1_invoke.sh -f examples/dynamic_vector_clocks/b1_3_node_simple_valid.txt -a dvc`: requiring `-f <file>` (flag and value) `-a <algorithm>` (flag and value); this example running the DVC implementation for an invalid/causal queueing scenario using 4 nodes. The shell script will calculate how much processes are needed to run the MPI program initially, and execute the `mpiexec` command dynamically for the specific implementation pased in.
2. The main algorithm is invoked; Process `0` is responsible for splitting the input line for each process (`1` to `N`) - which is sent at the start of the program.
3. After receiving the event list from Process `0` in Step 2: the main `process_loop` is executed by process `N` corresponding to the input row - and each event is determined and actioned upon. Each process holds onto a local clock, message/hold-back queue and floating-point number to add with message deliveries. On the latter - whenever a process is to send a broadcast/unicast message, it will generate a random floating-point number to add for corresponding receives and eventual deliveries.
4. Messages are thus sent and received - but **not** delivered unless the specific causal deliverability condition is met for either algorithm. Both algorithms implement a similar check on the incoming messages' clock. If both of these conditions are met, the message is delivered and the message's number is added to the process's number. Otherwise it is enqueued in a message/hold back queue:
    - The sender's value at its index in the message clock needs to be **exactly greater than 1** comparative to the value of its' value in the process's local clock.
    - Every other value in the message clock that is not of the sender is **less than or equal** to the receiving process's local clock value.
5. No matter on deliverability, both algorithms invoke checking the message queue on attempted message delivery after receiving a message. Until there are no messages in the queue (will exit if none were added on first pass), the process's local vector clock is checked against each message enqueued. If the message can be enqueued, the clocks are updated, the process's number is added with the message's number - and the loop starts again (this ensures re-checks are done on all messages when one is delivered for subsequent deliveries).
6. The `process_loop` is continually invoked until all events received in 2. are exhausted, and the process stops.

### Invocation

Invocating either algorithms' implementation is achieved by running the shell script that is provided within Phase 1's root directory - `phase1_invoke.sh`. This script expects two flag and valies `-f <file>` - the example input file you'd like to run the implementation against - and `-a <dvc|matrix>` - either `dvc` or `matrix` to invoke each algorithm's implementation respectfully. The script will calculate the number of processes needed based on the file given and will run `mpiexec` dynamically based on your input.

For example - running `b8_4_node_invalid.txt` for DVCs after cloning the repository:

```
git clone git@gitlab.eng.unimelb.edu.au:jsammut/comp90020-double-j.git
cd comp90020-double-j/phase1_mpi/
./phase1_invoke.sh -f examples/dynamic_vector_clocks/b8_4_node_invalid.txt -a dvc
```

The output of the script is the MPI logs and the event timeline for each process. Note the ordering may not always be in order due to the nature of the parallel nature of MPI programs!

```
|----- Process 4: ['r1', 'r3', 'r2'] -----|
-----------------------
Event #0 -> r1: (0)
-----------------------
Process 4 received number 9.444 from Process 1 @ 16:27:16.548878
This message satisfied the DVC causal deliverability condition. Delivering.
9.444 (message number) + 0 (current sum). Process 4's sum = 9.444

Checking messages in the message/hold back queue for deliverability
No messages are in the message/hold back queue
DVC after r1:	[[1, 1], [2, 0], [3, 0], [4, 0]]
Number Sum:	 9.444
-----------------------
Event #1 -> r3: (9.444)
-----------------------
Process 4 received number 4.01 from Process 3 @ 16:27:16.549633
This message did not satisfy the DVC causal deliverability condition. Will be enqueued.

Checking messages in the message/hold back queue for deliverability
This was the message that was just added - skipping it on first pass
Exhausted all messages. Breaking
DVC after r3:	[[1, 1], [2, 0], [3, 0], [4, 0]]
Number Sum:	 9.444
-----------------------
Event #2 -> r2: (9.444)
-----------------------
Process 4 received number 6.632 from Process 2 @ 16:27:16.549716
This message satisfied the DVC causal deliverability condition. Delivering.
6.632 (message number) + 9.444 (current sum). Process 4's sum = 16.076

Checking messages in the message/hold back queue for deliverability
This queued message satisfied the causal deliverability condition. Will be delivered.
4.01 (message number) + 16.076 (current sum). Process 4's sum = 20.086
No messages are in the message/hold back queue
DVC after r2:	[[1, 1], [2, 1], [3, 1], [4, 0]]
Number Sum:	 20.086
```

## Phase 2 - `phase2_sockets`

### Approach

The second phase of this project takes forward the Dynamic Vector Clock Algorithm using the MPI implementation from Phase 1 as the basis, now using **sockets** as the main means of p2p communication. To improve user experience, a Graphical User Interface (GUI) has been implemented using using [Kivy](https://kivy.org/) - a cross platform and open source library for developing Python applications with visual elements (including components such as windows, images, audio, buttons and more).

This phase focuses on using DVCs to provide functionality expected from modern multi-tenant chat applications, namely the ability to:
- Be able to join in (and conversely drop away) from chat rooms in real time
- Be able to have new members join the chat room without limit
- Be able to have their messages delivered in an order that makes sense (i.e. with casusal causal delivery). 

As these chat systems use sockets and run over the network, there's a real chance clients _may_ receive messages out-of-order due to heavy load or network congestion. We make use of DVCs with reliable broadcast to ensure that messages are always delivered according to a causal ordering, even if they're received by the client out of order.

### Implementation Overview

N.B. If you're not interested in the implementation, instructions on how to run can be found [here](#invocation-\--socket-implementation). 

#### Initial user input
Based on the `ENABLE_PEER_SERVER` param, peers are either manually gathered from user input, or are fetched from the peer server.
- When `ENABLE_PEER_SERVER` is set as `0`: peers will need to specify each peer they would like to connect with on joining the network. Once they're done, they'll need to specifying `f` or `finished` to connect to the network. 
- When `ENABLE_PEER_SERVER` is set as `1`: peers will connect with the central server that has been started at a specific IP address. The connecting peer will try to fetch the peers from the server with a `RegistryMessageType.GET_PEERS`, which the server will reply with a `RegistryMessageType.PEER_RESPONSE` with a peer list. If they're the first peer connected, they'll register themselves to the server's peer list with a `RegistryMessageType.REGISTER_PEER` message to the server and then register themselves with the registry server.

#### Initial peer setup (cloning)
After peers are gathered, the client broadcasts a `MessageType.HELLO` to all known peers, and then begins collecting all received messages. Peers receiving a `MessageType.HELLO` reply to the requesting peer with a `MessageType.HELLO_RESPONSE` that contains their current clock and undelivered message queue. The requesting peer initialises its clock to match the first clock it receives. It then joins its message queue with the message queue received from the peer whose clock it cloned, and then delivers all deliverable messages from the queue. Once the clock and queue are setup, the peer has a valid state and is ready to chat. The GUI is then launched.

#### Workers and data flow
After gathering initial user input, the client starts the following worker threads:
- `broadcastHandler`: for broadcasting and re-broadcasting messages to other peers
- `readWorker`: for reading incoming messages from each peer connection
- `handlerWorker`: for handling message delivery, and for processing `MessageType.HELLO` and `MessageType.HELLO_RESPONSE` messages
- `acceptWorker`: for accepting new connections from other peers

The `readWorker` continually performs non-blocking reads on any available readable sockets (i.e. sockets with non empty buffers), and passes any complete messages that are read to the handler's queue for processing.

The handler worker continually takes messages from its queue. 
- If the messages are `MessageType.BROADCAST_MESSAGE`, it rebroadcasts them and then attempts to deliver them (reliable broadcast, rebroadcast to all peers before delivering). Based on if the message's clock is deliverable at client's current clock state, the message is either immediately displayed in the UI, or queued in the `processMessageQueue` to be delivered once all casual predecessor messages have arrived.
- If the messages are `MessageType.HELLO`'s or `MessageType.HELLO_RESPONSE`'s, it makes no attempt to rebroadcast them and instead replies directly to the requesting client with an appropriate response.

When the send button is clicked in the Kivy GUI, the client's clock is updated, and then the message is stamped with the client's clock and added to the `broadcastHandler`'s queue, from which it is eventually taken and broadcast to other peers.


#### Communication
The client uses a connection based approach for p2p communication, with one socket opened for each peer and held open for the entire lifetime of the peer. All messages between the pair of peers are passed down the same connection stream. If a connection unexpectly closes or times out, that peer associated with that connection is considered to have failed and is removed from the client's list of peers. If all a client's peers have failed, then it displays a warning in the UI advising that future messages may fail to be delivered. A list of active peers is displayed in the top left of the GUI for user convenience.

The choice of a stream based approach is important - if a connection-per-message approach were taken, it's possible a client could become temporarily disconnected from their peers and fail to receive a message (this failure would be silent, as a message based approach doesn't actively check if peers are still reachable). In such a case, if the connection later becomes stable, the client would never be able to receive the next messages sent by their peers, as they would still be 'waiting' for the dropped message to be delivered. Using a connection based approach prevents this silent failure by alerting the user when they have become severed from their peers.

All messages sent in the system consist of a "message length" represented as a fixed width long, immediately followed by the actual message content (see below table for more details). Message content is a json that can contain a range of fields based on the message type.

|SIZE                           |TYPE                                 |DESCRIPTION                                   |
|-------------------------------|-------------------------------------|----------------------------------------------|
|4 bytes (platform independent) |Fixed width big-endian encoded long  |Represents length of message content in bytes |
|variable length                |json, encoded as a utf-8 byte string |Represents the content of the message         |


### Invocation - Socket Implementation

Our application works on the premise that new peers can join the system at any given time, whether that's by making use of a central peer registry server; or by manually keying in the addresses of peers. We provide instructions for both cases below.

#### .env parameters

Before continuing, make sure you have provided values for the following .env params:  

- `CLIENT_WORKER_THREADS`: the number of `broadcastHandler` / `readWorker` / `handlerWorker` threads a client will use.
- `PROTOCOL_PORT`: The port number that a client/peer will use for p2p communication
- `REGISTRY_PROTOCOL_PORT`: The port number used for communication with the peer registry server
- `ENABLE_PEER_SERVER`: Whether to enable the peer registry server. When disabled, clients must manually enter the ips of their peers. Takes values of 0 (disabled) or 1 (enabled).
- `ENABLE_NETWORK_DELAY`: Whether to enable simulated networking delay. Takes values of 0 (disabled) or 1 (enabled).
- `MOCK_NETWORK_DELAY`: The amount of time the simulated delay should last for. Value should be provided in seconds.

**Note:** For macOS users, the extension of the local loopback IP addresses beyond `127.0.0.1` may be required. If running Phase 2 on a macOS based machine, ensure that additional IPs beyond this address is able to be set.

#### Without a Peer Registry Server

Within a new terminal - clone the codebase (if not already done from phase 1) and change the working directory to `/phase2_sockets`. Ensure that in the `.env` file, `ENABLE_PEER_SERVER` is set to `0` (this is the default value)/

From there - you'll need to invoke a new client/peer via `client.py` with a specific IP address that it should listen on. For example - below is starting up a client/peer with `127.0.0.1` as its listining IP:

```
python3 client.py 127.0.0.1
```

The running client/peer will then start its respective workers; and then loop for other client/peer IPs/hostnames to connect to. Once completed with the respective client/peers - enter `f` or `finished`:

```
╰─ python3 client.py 127.0.0.1
[INFO   ] [Logger      ] Record log in /home/joel/.kivy/logs/kivy_24-05-11_81.txt
[INFO   ] [Kivy        ] v2.3.0
[INFO   ] [Kivy        ] Installed at "/home/joel/miniconda3/lib/python3.12/site-packages/kivy/__init__.py"
[INFO   ] [Python      ] v3.12.1 | packaged by Anaconda, Inc. | (main, Jan 19 2024, 15:51:05) [GCC 11.2.0]
[INFO   ] [Python      ] Interpreter at "/home/joel/miniconda3/bin/python"
[INFO   ] [Logger      ] Purge log fired. Processing...
[INFO   ] [Logger      ] Purge finished!
[INFO   ] [Factory     ] 195 symbols loaded
[INFO   ] [Image       ] Providers: img_tex, img_dds, img_sdl2, img_pil (img_ffpyplayer ignored)
[INFO   ] [Text        ] Provider: sdl2
[INFO   ] [Window      ] Provider: sdl2
[INFO   ] [GL          ] Using the "OpenGL" graphics system
[INFO   ] [GL          ] Backend used <sdl2>
[INFO   ] [GL          ] OpenGL version <b'4.6 (Compatibility Profile) Mesa 21.2.6'>
[INFO   ] [GL          ] OpenGL vendor <b'AMD'>
[INFO   ] [GL          ] OpenGL renderer <b'AMD Radeon RX 5700 XT (NAVI10, DRM 3.42.0, 5.15.0-105-generic, LLVM 12.0.0)'>
[INFO   ] [GL          ] OpenGL parsed version: 4, 6
[INFO   ] [GL          ] Shading version <b'4.60'>
[INFO   ] [GL          ] Texture max size <16384>
[INFO   ] [GL          ] Texture max units <32>
[INFO   ] [Window      ] auto add sdl2 input provider
[INFO   ] [Window      ] virtual keyboard not allowed, single mode, not docked
App configuration (.env + argv): {
    "CLIENT_WORKER_THREADS": "4",
    "PROTOCOL_PORT": "9876",
    "REGISTRY_PROTOCOL_PORT": "9877",
    "ENABLE_PEER_SERVER": "0",
    "ENABLE_NETWORK_DELAY": "0",
    "MOCK_NETWORK_DELAY": "5",
    "CLIENT_LISTEN_IP": "127.0.0.1"
}
Enter peer IPs/hostnames [enter 'finished' or 'f' to continue]
Enter hostname: 127.0.0.2
Added peer at 127.0.0.2
Enter hostname: f
[INFO] Client listening at 127.0.0.1 on port 9876
[INFO] Connecting to the network, please wait...
[INFO] Initialised with clock [['5898c2b0-f1b1-42ca-9efe-8f5d16c5d87c', 0], ['93be79c8-91b4-4755-90c9-7542cb7729c9', 0]]
[INFO   ] [Clipboard   ] Provider: xclip
[INFO   ] [CutBuffer   ] cut buffer support enabled
[INFO   ] [Base        ] Start application main loop
[INFO   ] [GL          ] NPOT texture support is available

```

Other clients/peers that wish to connect to the network will need to be connected in a similar fashion - and **with a different IP/hostname**. 

Once the client has connected to at least one other peer, a local Kivy window will appear where they can enter in messages to be broadcast to other peers. 
- These messages can include markup to allow styling of size, text colour, boldness, etc.
- The client can keep track of peers they're connected to by checking the top left corner of the window.
- If the client ever has no peers remaining, an error is displayed in the top right corner of the window.
- Peers may join and leave the network as they desire.

The images below show two peers that have just exchanged messages. The peer at `127.0.0.2` has added styling to their message by sending `[size=50]Hi! Did you know we support [color=ff0000]markup[/color][/size]`.

![P2P Messaging App - Without a central peer registry (client at 127.0.0.1)](/phase2_sockets/images/ClientExample1.png)
![P2P Messaging App - Without a central peer registry (client at 127.0.0.2)](/phase2_sockets/images/ClientExample2.png)

#### With simulated network delay

To simulate network delay for communication between processes, the following changes are required in the `.env` file.
- `ENABLE_NETWORK_DELAY` should be set to `1`
- `MOCK_NETWORK_DELAY` should be set to a reasonable delay. I found `5` allowed the delay to be clearly observed, without making me too impatient.

The client can then be invoked as per the instructions for running without the peer registry server, except that an additional argument should be provided to specifiy the IP whose messages should be delayed. For instance, to run the client at `127.0.0.1` while simulate the delay of messages from `127.0.0.2`, use the following command:

```
python3 client.py 127.0.0.1 127.0.0.2
```

I have found that the easiest way to test causal delivery is functioning as expected is as follows:
1. Run a client at `127.0.0.1` and `127.0.0.2`, with both throttling some unused address (e.g. `127.0.0.99`)
2. Run another client at `127.0.0.3` that delays messages from `127.0.0.1`. 
3. You can then send a message from `127.0.0.1`, then send another from `127.0.0.2` once the first message is received.
4. The client at `127.0.0.3` will not be able to receive the message from `127.0.0.2` until the delayed message from `127.0.0.1` is finally received, as `127.0.0.2`'s message is causally dependant on the delayed message.


#### With a Peer Registry Server

Within a new terminal - clone the codebase (if not already done from phase 1) and change the working directory to `/phase2_sockets`. Ensure that in the `.env` file, `ENABLE_PEER_SERVER` is set to `1` to enable the central peer registry server. You might want to also change its port via `REGISTRY_PROTOCOL_PORT` in `.env`

From there - you'll need to start the server **first** by `server.py` with a specific IP address that it should should listen on. For example - below is starting up the server with `127.0.0.1` as its listening IP:

```
python3 server.py 127.0.0.1
```

The server will then start up and start listening on the respective IP and port specified:

```
╰─ python3 server.py 127.0.0.1
Server listening at 127.0.0.1 on port 9877
```

From here - similar to the case where [clients/peers connect without a central peer registry server](#without-a-peer-registration-server), new clients/peers will need to be started and thus will register with the server and join the network. Unlike the above though, `client.py` now expects **two** arguments: the first as the client/peer's IP, and the second as the server's IP. For example - starting a client/peer with address `127.0.0.2` connecting to the central peer registry server at `127.0.0.1`: 

```
python3 client.py 127.0.0.2 127.0.0.1
```

Running the above will map this client/peer's IP: and based on if this is the first peer (or not) as explored in the [invocation](#invocation-1) section will either register with the server and await new client/peer connections - or say `hello` to all other client/peers (message merging) and then register itself with the server (and thus network). There is **no need** to specify IPs for other client/peers in this scenario - as this is the job of the server to direct to client/peers that join in at any time:

```
╰─ python3 client.py 127.0.0.2 127.0.0.1
[INFO   ] [Logger      ] Record log in /home/joel/.kivy/logs/kivy_24-05-11_83.txt
[INFO   ] [Kivy        ] v2.3.0
[INFO   ] [Kivy        ] Installed at "/home/joel/miniconda3/lib/python3.12/site-packages/kivy/__init__.py"
[INFO   ] [Python      ] v3.12.1 | packaged by Anaconda, Inc. | (main, Jan 19 2024, 15:51:05) [GCC 11.2.0]
[INFO   ] [Python      ] Interpreter at "/home/joel/miniconda3/bin/python"
[INFO   ] [Logger      ] Purge log fired. Processing...
[INFO   ] [Logger      ] Purge finished!
[INFO   ] [Factory     ] 195 symbols loaded
[INFO   ] [Image       ] Providers: img_tex, img_dds, img_sdl2, img_pil (img_ffpyplayer ignored)
[INFO   ] [Text        ] Provider: sdl2
[INFO   ] [Window      ] Provider: sdl2
[INFO   ] [GL          ] Using the "OpenGL" graphics system
[INFO   ] [GL          ] Backend used <sdl2>
[INFO   ] [GL          ] OpenGL version <b'4.6 (Compatibility Profile) Mesa 21.2.6'>
[INFO   ] [GL          ] OpenGL vendor <b'AMD'>
[INFO   ] [GL          ] OpenGL renderer <b'AMD Radeon RX 5700 XT (NAVI10, DRM 3.42.0, 5.15.0-105-generic, LLVM 12.0.0)'>
[INFO   ] [GL          ] OpenGL parsed version: 4, 6
[INFO   ] [GL          ] Shading version <b'4.60'>
[INFO   ] [GL          ] Texture max size <16384>
[INFO   ] [GL          ] Texture max units <32>
[INFO   ] [Window      ] auto add sdl2 input provider
[INFO   ] [Window      ] virtual keyboard not allowed, single mode, not docked
App configuration (.env + argv): {
    "CLIENT_WORKER_THREADS": "4",
    "PROTOCOL_PORT": "9876",
    "REGISTRY_PROTOCOL_PORT": "9877",
    "ENABLE_PEER_SERVER": "1",
    "ENABLE_NETWORK_DELAY": "0",
    "MOCK_NETWORK_DELAY": "5",
    "CLIENT_LISTEN_IP": "127.0.0.2",
    "PEER_REGISTRY_IP": "127.0.0.1"
}
[INFO] Retrieving peers from registry server...
[INFO] Received peers from registry:  []
[INFO] Registry had no valid peers, registering self
[INFO] Starting with no peers - waiting for at least one peer to establish connection...
[INFO] Client listening at 127.0.0.2 on port 9876

```

Once connected, the client will appear identical to no-peer registry server flow.

#### With a Peer Registry Server AND network delay

If you intend to run with both a registry server and a network delay, you must specify the client ip, then the server ip, then the throttled ip. For example, to run a client at `127.0.0.2` with a registry server at `127.0.0.1` and a throttled ip at `127.0.0.99`, use the following command:

```
python3 client.py 127.0.0.2 127.0.0.1 127.0.0.99
```

Note that `.env` params should be configured as per the instructions in the network delay and registry server sections of the readme.


## Presentation

Team Double-J's presentation presented on this project can be found in the `/presentation` directory.

## Bibliography
[1] N. Meghanathan. Module 6.2.3 Matrix Algorithm Causal Delivery of Messages. (Nov. 12, 2013). Accessed: Mar. 13, 2024. [Online video]. Available: https://www.youtube.com/watch?v=WgTx7BHWzts.<br/>
[2] T. Landes. "Dynamic Vector Clocks for Consistent Ordering of Events in Dynamic Distributed Applications." in International Conference on Parallel and Distributed Processing Techniques and Applications, Las Vegas, Nevada, USA, 2006, pp.1-7.<br/>
[3] L. Lafayette. (2021). The Spartan HPC System at the University of Melbourne [PDF]. Available: https://canvas.lms.unimelb.edu.au/courses/105440/files/7018506/download?download_frd=1.<br/>
[4] L. Dalcin. "Tutorial". MPI for Python. https://mpi4py.readthedocs.io/en/stable/tutorial.html (accessed Mar. 13, 2024).<br/>
[5] Jurudocs. "Format a datetime into a string with milliseconds". Stack Overflow. https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds (accessed Mar. 13, 2024).<br/>
[6] M. Toboggan. "How to get a random number between a float range?". Stack Overflow. https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range (accessed Mar. 15, 2024).<br/>
[7] NumPy Developers. "numpy.zeros". NumPy. https://numpy.org/doc/stable/reference/generated/numpy.zeros.html (accessed Mar. 16, 2024).<br/>
[8] New York University. "Non-blocking Communication". GitHub Pages. https://nyu-cds.github.io/python-mpi/03-nonblocking/ (accessed Mar. 24, 2024).<br/>
[9] L. Dalcin. "mpi4py.MPI.Message". MPI for Python. https://mpi4py.readthedocs.io/en/stable/reference/mpi4py.MPI.Message.html (accessed Mar. 30, 2024).<br/>
[10] W3Schools. "Python String split() Method". W3Schools. https://www.w3schools.com/python/ref_string_split.asp (accessed Mar. 30, 2024).<br/>
[11] C. Kolade. "Python Switch Statement - Switch Case Example". freeCodeCamp. https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ (accessed Mar. 30, 2024).<br/>
[12] spiderman. "How to find string that start with one letter then numbers". FME Community. https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 (accessed Mar. 30, 2024).<br/>
[13] TutorialsTeacher. "Grouping in Regex". TutorialsTeacher. https://www.tutorialsteacher.com/regex/grouping (accessed Mar. 30, 2024).<br/>
[14] hoju. "Extract part of a regex match". Stack Overflow. https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match (accessed Mar. 30, 2024).<br/>
[15] M. Breuss. "How to Check if a Python String Contains a Substring". Real Python. https://realpython.com/python-string-contains-substring/ (accessed Mar. 30, 2024).<br/>
[16] Python Principles. "How to convert a string to int in Python". Python Principles. https://pythonprinciples.com/blog/python-convert-string-to-int/ (accessed Mar. 30, 2024).<br/>
[17] TransparenTech LLC. "Generate a UUID in Python". UUID Generator. https://www.uuidgenerator.net/dev-corner/python/ (accessed Mar. 30, 2024).<br/>
[18] W3Schools. "Python - List Comprehension". W3Schools. https://www.w3schools.com/python/python_lists_comprehension.asp (accessed Mar. 30, 2024).<br/>
[19] greye. "Get loop count inside a for-loop [duplicate]". Stack Overflow. https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop (accessed Mar. 30, 2024).<br/>
[20] G. Ramuglia. "Using Bash to Count Lines in a File: A File Handling Tutorial". I/O Flood. https://ioflood.com/blog/bash-count-lines/ (accessed Mar. 30, 2024).<br/>
[21] H. Sundaray. "How to Use Bash Getopts With Examples". KodeKloud. https://kodekloud.com/blog/bash-getopts/ (accessed Mar. 30, 2024).<br/>
[22] Linuxize. "Bash Functions". Linuxize. https://linuxize.com/post/bash-functions/ (accessed Mar. 30, 2024).<br/>
[23] Nick. "How can I add numbers in a Bash script?". Stack Overflow. https://stackoverflow.com/questions/6348902/how-can-i-add-numbers-in-a-bash-script (accessed Mar. 30, 2024).<br/>
[24] GeeksForGeeks. "Command Line Arguments in Python". GeeksForGeeks. https://www.geeksforgeeks.org/command-line-arguments-in-python/ (accessed Mar. 30, 2024).<br/>
[25] V. Hule. "Generate Random Float numbers in Python using random() and Uniform()". PYnative. https://pynative.com/python-get-random-float-numbers/ (accessed Apr. 1, 2024).<br/>
[26] bhaskarc. "Iterating over a 2 dimensional python list [duplicate]". Stack Overflow. https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list (accessed Apr. 1, 2024).<br/>
[27] note.nkmk.me. "How to return multiple values from a function in Python". note.nkmk.me. https://note.nkmk.me/en/python-function-return-multiple-values/ (accessed Apr. 2, 2024).<br/>
[28] A. Luiz. "How do you extract a column from a multi-dimensional array?". Stack Overflow. https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array (accessed Apr. 2, 2024).<br/>
[29] W3Schools. "Python Remove Array Item". W3Schools. https://www.w3schools.com/python/gloss_python_array_remove.asp (accessed Apr. 2, 2024).<br/>
[30] nobody. "Python regular expressions return true/false". Stack Overflow. https://stackoverflow.com/questions/6576962/python-regular-expressions-return-true-false (accessed May. 6, 2024).<br/>
[31] A. Jalli. "Python Switch Case -- Comprehensive Guide". Medium. https://medium.com/@artturi-jalli/python-switch-case-9cd0014759e4 (accessed May. 4, 2024).<br/>
[32] Linuxize. "Bash if..else Statement". Linuxize. https://stackoverflow.com/questions/67428689/how-to-pass-multiple-flag-and-multiple-arguments-in-getopts-in-shell-script (accessed May. 4, 2024).<br/>
[33] Kivy. "Kivy: The Open Source Python App Development Framework.". Kivy. https://kivy.org/ (accessed May. 4, 2024).<br/>
[34] R. Strahl. "Getting Images into Markdown Documents and Weblog Posts with Markdown Monster". Medium. https://medium.com/markdown-monster-blog/getting-images-into-markdown-documents-and-weblog-posts-with-markdown-monster-9ec6f353d8ec (accessed May. 5, 2024).<br/>
[35] cantdutchthis. "Changing image size in Markdown". Stack Overflow. https://stackoverflow.com/questions/14675913/changing-image-size-in-markdown (accessed May. 5, 2024).<br/>