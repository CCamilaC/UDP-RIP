

Hello everyone, this repository is intended for my project in the Computer Networks course that I took during the 2025/2 semester. I hope you like it!

#  UDPRIP: Distance Vector Routing Protocol
## Introduction

In this assignment we will develop UDPRIP, a routing software that uses distance vectors to distribute routes. We will implement support for link weights and route measurements.

    This assignment can be submitted by groups of up to two students.

## Virtual Topology

You should implement a program that emulates a virtual topology. We will create IP addresses in the 127.0.1.0/24 prefix on the loopback interface in your computer. Each router will be bound (using the bind() function) to a local IP address. Each router will use a UDP socket bound to its respective address to exchange messages with other routers.

Your program should have a command-line interface and support two commands to manage the virtual topology:

    add <ip> <weight>: This command will add a virtual link between the current router (that is, the router where the command was run) and the router associated with the given IP. When computing routes with the lowest weights, the weight for transmitting data from the current router to the neighboring router is the given weight.

    del <ip>: This command removes a virtual link between the current router and the router given by ip. Removing a link from the topology emulates a link failure and should lead to routers choosing alternate routes.

A virtual link between routers allows data transmission in only one direction. For example, when executing add <R2> <weight> on router R1, route announcements will be sent from R1 to R2. Traffic using these routes will flow in the opposite direction (from R2 to R1). Creation of bidirectional links requires executing the add command on both routers connected to a link.

Virtual links are used to send data. Link weights are used to compute the best routes. The commands above allow us to generate arbitrary virtual topologies and allow us to emulate failures or test route recomputation.
Adding IP Addresses to the Loopback Interface

You can add an IP address to an interface on Linux using the commands below. Other operating systems have similar commands, but it may be easiest to use a virtual machine. Note that the IP address should contain the prefix length identifying the network to which the interface is connected.

ip addr add <ip>/<prefixlen> dev <interface>

To add IP addresses to the loopback interface, we can execute the commands below. The files accompanying this assignment includes a lo-addresses.sh script that executes the commands needed to add and remove addresses from the loopback interface.

ip addr add 127.0.1.1/32 dev lo
ip addr add 127.0.1.2/32 dev lo
...
ip addr add 127.0.1.16/32 dev lo

    On Linux, we add addresses to the loopback interface, which is named lo. On macOS, the loopback interface may be named lo0 instead.

    Note that the addresses we add are in the 127.0.1.0/24 prefix, not 127.0.0.0/24 prefix.

We will execute the routing program multiple times, each time binding to different IP addresses. Each program will have their UDP socket. Messages will be exchanged between programs. This is equivalent to an operating mode where programs execute on different computers.
Example

We will use the topology below as an example throughout this specification. All links are bidirectional:

                   127.0.1.1
                       ^
                       |
                       10
                       |
                       v
127.0.1.2 <--10--> 127.0.1.5 <--10--> 127.0.1.3
                       ^
                       |
                       10
                       |
                       v
                   127.0.1.4

To create this topology, we need to execute the following commands in the router bound to IP address 127.0.1.5:

add 127.0.1.1 10
add 127.0.1.2 10
add 127.0.1.3 10
add 127.0.1.4 10

In all other routers, we need to execute the command below:

add 127.0.1.5 10

### Message Encoding and Semantics

All messages exchanged are encoded using JSON, an encoding format widely used in Web applications. You can use JSON encoding and decoding libraries like Python’s JSON module. JSON is pure text and can be easily inspected by humans, which should ease debugging.

All messages exchanged in this assignment will be JSON objects with at least three fields:

    source: Specifies the IP address of the router that originated the message.

    destination: Specifies the IP address of the router the message is sent to.

    type: Specifies the type of the message, its semantics, and any additional fields. In this assignment, we will implement three types of messages: data, update, and trace messages, described next.

### Data Messages

Data messages have their type field with a value set to "data". Data messages have all three fields described previously and a payload field that contains any string, which is the data to be transferred.

If a router is not the destination of a data message, it should forward the message towards the destination. If a router receives a data message destined to it (that is, it is the message's destination), it should print its payload on the screen. Below is an example data message:

{
    "type": "data",
    "source": "127.0.1.2",
    "destination": "127.0.1.1",
    "payload": "{\"destination\": \"127.0.1.2\", \"type\": \"trace\", ...}"
}

### Update Messages

Your router must send messages containing route updates, or just updates, periodically to each of its neighbors. A neighbor is another router that is directly connected. Neighbors are added and removed through the command-line interface using the add and del commands.

Update messages must have their type field set to "update". The source and destination fields must be set to the IP address of the router generating the message and the IP address of the intended neighbor, respectively. Finally, updates should also contain a distances field containing a JSON dictionary informing the neighbor of the best routes known by the current router. More specifically, the distances field should be a dictionary containing key-value pairs mapping a destination address (belonging to a third router) to the distance to reach that destination. Below we show a route update message sent by router 127.0.1.5 to 127.0.1.1:

{
    "type": "update",
    "source": "127.0.1.5",
    "destination": "127.0.1.1",
    "distances": {
        "127.0.1.4": 20,
        "127.0.1.5": 10,
        "127.0.1.2": 20,
        "127.0.1.3": 20
    }
}

To minimize the impact of the count-to-infinity problem, your program should implement Split Horizon: Update messages sent to a neighboring router R should not contain any routes learned from R itself.
### Trace Messages

Your router must also be able to handle trace messages. Trace messages are used to measure the route between any two routers in the network. In addition to the type, source, and destination fields, a trace message also has a routers field, which stores the list of routers already traversed by the trace message.

When it receives a trace message, a router must first add its IP address to the end of the routers list. If the router is not the destination of a trace, then it must forward the trace toward the destination as normal. If the router is the trace's destination, it must send a response to the source. A response message is simply a data message containing the entire trace message as its payload. In other words, the trace's results must be sent back to the source inside a data message.

On top of the add and del commands described above to create the virtual topology, your program should also support a trace command which will generate a trace message. The trace command has the following format:

    trace <ip>: Send a trace message from the current router to the given IP.

Below we show an example trace message originated by router 127.0.1.1 sent to router 127.0.1.2. Router 127.0.1.2 must encapsulate the trace result in a data message and send it as a payload back to 127.0.1.1. Example message received by 127.0.1.2:

{
    "type": "trace",
    "source": "127.0.1.1",
    "destination": "127.0.1.2",
    "routers": ["127.0.1.1", "127.0.1.5"]
}

The trace result contains the IP address of the destination:

{
    "type": "trace",
    "source": "127.0.1.1",
    "destination": "127.0.1.2",
    "routers": ["127.0.1.1", "127.0.1.5", "127.0.1.2"]
}

The response is a data message containing the entire trace as the payload:

{
  "type": "data",
  "source": "127.0.1.2",
  "destination": "127.0.1.1",
  "payload": "{\"type\": \"trace\",
               \"source\": \"127.0.1.1\",
               \"destination\": \"127.0.1.2\",
               \"routers\": [\"127.0.1.1\", \"127.0.1.5\", \"127.0.1.2\"]
              }"
}

## Distance Vector Routing

Your program should implement a distance vector routing protocol. It should send routing updates to neighboring routers containing the best paths for all known destinations.

Your router should send routing updates periodically, and recompute routes automatically as it receives routing updates from neighboring routers. When forwarding a packet, your router should search its routing table and use the shortest route it knows to that destination. To do this, your router must keep track of route distances, and which neighbor each route was learned from.

Your router should remove routes from its routing table learned from a neighbor when that neighbor stops sending routing updates. The lack of routing updates is an indication that the router is off, crashed, or somehow misbehaving. In particular, your program should remove routes from a neighbor after not receiving an update for 4π4π seconds, where ππ is the period between routing updates (specified below).

The router must drop messages for any destinations it cannot reach (that is, any destination it doesn't know a route to). If there are multiple routes, your program can choose any route to use.

Note that when the add <R2> <weight> command is executed on a router R1, routing update messages are sent only in one direction (from R1 to R2), and traffic flows in the reverse direction (R2 may choose routes distributed by R1). On the example topology, if only the add 127.0.1.1 10 is executed on router 127.0.1.5 (and add 127.0.1.5 10 is not executed on router 127.0.1.1), then no device will be able to send data to 127.0.1.1, and 127.0.1.1 would be able to send data to any other device. Also, 127.0.1.1 would receive complete routing update messages from 127.0.1.5, exactly as shown in the example update message above.
## Extra Credit

Additional functionality can be considered as extra credit:

    Load balancing: You can extend your router to use multiple routes toward a destination if they have the same distance. The router must install multiple entries in its forwarding table (or some equivalent implementation), and choose the next router at random from the set of best routes whenever it needs to forward a packet to the destination. (10% extra)

    Control messages: Define and implement functionality for a new message type that notifies sources when their packets are dropped because no route to the destination is known. (5% extra)

Implementation and User Interface

You must implement UDPRIP using UDP sockets in any programming language of your choice. Your implementation should interoperate with other implementations; you can test your router with your colleagues' routers. You should also test your router using the provided test cases.
## Startup

Your UDPRIP instance should be executed on the command line as follows:

./router.py <address> <period> [startup]

Where address specifies on which IP address the router should bind(), and period specifies the time between routing update messages (ππ). Finally, the optional startup parameter should be a file name containing add and del commands that should be processed during startup. The startup files are used to build complex virtual topologies when routers start executing.

    Implement the interface specification precisely. We have scripts to start the your program, and the scripts rely on the command-line interface being exactly as described.

All routers should use UDP port 55151 for communication.

    In Python, use socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0) to create a UDP socket. You are also free to use other libraries to create the UDP socket.

## Execution and Termination

Your router should read add, del, and trace commands from the keyboard. Each router must print on the screen only the payload of data messages destined to it. If you need to print messages during debugging, consider using a logging library to log to a file, or disable the debug output before submitting your assignment.

A router should stop executing when it receives a keyboard interrupt (ctrl-c), or when the user types quit on the command line.
Tests

A set of tests is also available on the course website, which should allow you to run preliminary tests on your router. You are free to create and submit additional test topologies.
Grading

Any incoherence or ambiguity in this spec should be notified to the instructor. Confirmed issues will be awarded extra credit. This assignment can be implemented individually or in pairs.

You should submit the source code for your program. For compiled languages, include documentation and metadata (for example, a Makefile) to ease compilation of your program.

Abiding by the specified command-line interface is going to be considered in your final grade. Programs that do not follow the specified command-line interface may be penalized up to 25% of the assignment grade.

You should also submit a PDF containing documentation describing (i) how you implemented the periodic updates; (ii) what data structures are used to keep track of the next routers on the paths to each destination, (iii) and how you dealt with the removal of stale routes when a neighbor router stops sending updates.

# How to run

<p align='center'>
   <img src="./images/example.gif" width="700"/>
</p>

# Short test
For this small test, a network like the one described below was used, and the following steps, also present in the diagram, were executed
<p align="center">
  <img src="./images/diagramNetwork.png" width="700" />
</p>

In the terminal, it is expected to see something like the one shown in the figure below.

<p align="center">
  <img src="./images/terminal.png" width="700" />
</p>

# Authors

The authors are Camila Chagas Carvalho and Luiza Calheiros Lei. There is no license for the use of this repository.