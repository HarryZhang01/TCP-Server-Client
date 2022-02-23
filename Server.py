import socket
import selectors
import signal
import sys

# Create selector object as a global variable to monitor input output events
selectorObject = selectors.DefaultSelector()
# Create empty global dictionary to keep track of connected clients
connectedUsers = {}
# Create empty global dictionary that keep track of all follow terms of each user
userFollowDict = {}

def main():
    # Signal catcher to monitor for Ctrl-C events
    signal.signal(signal.SIGINT, handler)

    # Create server socket that can communicate over TCP
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Server socket is bound to default 'localhost' and chooses a random non-reserved port to bind to
    serverSocket.bind(('', 50000))

    # Server allows for up to 10 connections at once
    serverSocket.listen(10)

    # Disables blocking on server socket
    serverSocket.setblocking(False)

    # Server socket object is registered into the selector to monitor for IO events
    selectorObject.register(serverSocket, selectors.EVENT_READ, acceptConnection)

    # Displays the location clients can connect to to connect to the server
    print('The server is ready to receive client connections at port: ' + str(serverSocket.getsockname()))
    print('Waiting for incoming client connections ...')

    # Enter into a endless loop to accept connection or to read and write data
    while True:
        events = selectorObject.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


# Function that handles making new connections with client sockets
def acceptConnection(serverSocket, mask):
    # Client socket is connected to server socket
    connectedSocket, address = serverSocket.accept()

    # Receives the registration sent by the client each time there is a new connection
    registrationMessage = connectedSocket.recv(1024).decode()

    # Split up the registration message into a list to check for format
    registrationList = registrationMessage.split(' ')

    # If registration message is the incorrect format then the connection is closed and error message is sent to the
    # client
    if registrationList[0] != 'REGISTER' or registrationList[2] != 'CHAT/1.0' or len(registrationList) != 3:
        connectedSocket.sendall('400 Invalid Registration'.encode())
        connectedSocket.close()
        return

    # The client user name is extracted from the registration message
    clientName = registrationList[1]

    # If the user tries to register onto the server with the username "all" their login request will be rejected
    if clientName == 'all':
        connectedSocket.sendall('400 Invalid Username'.encode())
        connectedSocket.close()
        return

    print(f'Accepted connection from client address: {address}')

    # Check if a user with the extracted client user name is already connected to the server
    for key in connectedUsers:
        if connectedUsers[key] == clientName:
            connectedSocket.sendall('401 Client already registered'.encode())
            # If another user is already connected with the same name the socket connection is closed and function is
            # exited
            connectedSocket.close()
            return

    # Once the client socket passes all tests above a successful message is sent to the client
    connectedSocket.sendall('200 Registration successful'.encode())

    # The client user name and their associated socket information is stored inside the dictionary
    connectedUsers[connectedSocket] = clientName

    # The client's follow list is created to have them following their own @ and @all
    userFollowDict[connectedSocket] = {f'@{clientName}', '@all'}

    # Server is now ready to receive messages from clients
    print(f"Connection to client established, waiting to receive messages from user '{clientName}'")
    # connectedSocket.setblocking(False)

    # Register the newly connected server with the selector to monitor for IO activities
    selectorObject.register(connectedSocket, selectors.EVENT_READ, readInput)


# Function that handles all incoming messages sent by clients
def readInput(connectedSocket, mask):
    # Attempts to receive all incoming messages from the client
    incomeData = connectedSocket.recv(1024).decode()
    sourceClient = connectedUsers[connectedSocket]

    # If a client disconnect message is detected then the client is removed from the dictionary and the connection is
    # closed
    if (incomeData.startswith('DISCONNECT')) or ('!exit' in incomeData):
        print(f'Disconnecting user {connectedUsers[connectedSocket]}')
        del connectedUsers[connectedSocket]
        del userFollowDict[connectedSocket]
        connectedSocket.sendall('DISCONNECT CHAT/1.0'.encode())
        selectorObject.unregister(connectedSocket)
        connectedSocket.close()

    # If user wants to view the list of active users server sends back a string of all active users on server
    elif '!list' in incomeData:
        returnString = ""
        for key in connectedUsers:
            returnString += connectedUsers[key] + " "
        connectedSocket.sendall(returnString.encode())

    # Sends all user's currently following terms
    elif '!follow?' in incomeData:
        returnString = ", ".join(userFollowDict[connectedSocket])
        connectedSocket.sendall(returnString.encode())

    # Allows user to follow a word
    elif '!follow' in incomeData:
        keyWord = '!follow'
        beforeWord, keyWord, afterWord = incomeData.partition(keyWord)

        afterWord = afterWord.strip('\n ')

        # Does not perform any actions if the word is already being followed by the user
        if afterWord in userFollowDict[connectedSocket]:
            returnString = f'{afterWord} is already being followed'
            connectedSocket.sendall(returnString.encode())
            return

        # If the word is not yet followed the word is added into the following set
        else:
            userFollowDict[connectedSocket].add(afterWord)
            returnString = f'Now following {afterWord}'
            connectedSocket.sendall(returnString.encode())

    # Allows the user to unfollow a word they are currently following
    elif '!unfollow' in incomeData:
        keyWord = '!unfollow'
        beforeWord, keyWord, afterWord = incomeData.partition(keyWord)

        afterWord = afterWord.strip('\n ')

        # Users are not allowed to unfollow @all and themselves
        if afterWord == '@all' or afterWord == f'@{connectedUsers[connectedSocket]}':
            returnString = f'Cannot unfollow {afterWord}'
            connectedSocket.sendall(returnString.encode())
            return

        # Removes word from following list
        if afterWord in userFollowDict[connectedSocket]:
            userFollowDict[connectedSocket].remove(afterWord)
            returnString = f'No longer following {afterWord}'
            connectedSocket.sendall(returnString.encode())

        # If the word was never followed then notifies the user
        else:
            returnString = f'{afterWord} is not one of the followed words'
            connectedSocket.sendall(returnString.encode())
            return

    # Allows user to attach and send a file over the server
    elif '!attach' in incomeData:

        # Extract file information from input
        # Breaks incoming message into word list and erases the colon symbol from all words
        fileData = incomeData.split()
        fileDataClean = [word.replace(':', '') for word in incomeData.split()]
        fileName = fileData[2]

        # Determine the length of the file
        contentLengthBytes = connectedSocket.recv(1024)
        fileLength = int(contentLengthBytes[16:])

        # Make another list filled with recipients that will receive the message if they are following a word in the
        # message
        recipients = [x for x in connectedUsers if x != connectedSocket and userFollowDict[x].intersection(fileDataClean)]

        # Sends file information to every user that is suppose to receive it
        for key in recipients:
            key.sendall(f'Incoming file: {fileName}'.encode())
            key.sendall(f'Origin: {fileDataClean[1]}'.encode())
            key.sendall(contentLengthBytes)

        # Then send the file chunk by chunk
        for i in range(0, fileLength, 1024):
            chunk = connectedSocket.recv(1024)
            for key in recipients:
                key.sendall(chunk)

    # If else the message is displayed on the server and sent to all other clients who is following the same word
    # that is contained inside the incoming message other than the sender themselves
    else:
        print(f'Received message from user {sourceClient}: {incomeData}')

        # Breaks incoming message into word list and erases the colon symbol from all words
        wordListClean = [word.replace(':', '') for word in incomeData.split()]

        # Make another list filled with recipients that will receive the message if they are following a word in the
        # message
        recipients = [x for x in connectedUsers if x != connectedSocket and userFollowDict[x].intersection(wordListClean)]

        # Send to all recipients who should receive the message
        for key in recipients:
            key.sendall(incomeData.encode())


# Special signal handler that detects Ctrl-C and prints error message before terminating program
def handler(incomingSignal, frame):
    print('Interrupt received, shutting down ...')
    for key in connectedUsers:
        key.sendall('DISCONNECT CHAT/1.0'.encode())
    sys.exit(0)


if __name__ == '__main__':
    main()
