import socket
import sys
import signal
from urllib.parse import urlparse
import selectors

# Create selector object as a global variable to monitor input output events
selectorObject = selectors.DefaultSelector()


def main(self):
    global clientSocket
    # Create client socket object with TCP communication protocols
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Register read and send events with the selector so they can be monitored simultaneously
    selectorObject.register(clientSocket, selectors.EVENT_READ, incomingMessage)
    selectorObject.register(sys.stdin, selectors.EVENT_READ, outgoingMessage)

    # Username of the client is extracted from the command line arguments
    global userName
    userName = sys.argv[1]

    # Command line arguments are further parsed into distinct sections
    parsedURL = urlparse(sys.argv[2])

    # Check if the entered command protocol is 'chat' or not, if wrong protocol is entered program terminates
    assert parsedURL.scheme == 'chat', 'Invalid Protocol'

    # Host name and port number is split into a tuple
    address = parsedURL.netloc.split(':')

    # Signal catcher to monitor for Ctrl-C events
    signal.signal(signal.SIGINT, handler)

    # Checks if the hostname is correct and whether the port number is valid
    if (address[0] != 'localhost') or (int(address[1]) < 10000):
        sys.exit('Wrong hostname or port number provided. Program terminated')

    # If everything passes the client socket is connected to the server
    print('Connecting', userName, 'to server ...')
    clientSocket.connect((address[0], int(address[1])))
    print('Connection to server established. Sending intro message ...')

    # Client registration message is sent to the server
    clientSocket.send(f'REGISTER {userName} CHAT/1.0'.encode())

    # Response of server to the registration message is received and stored
    registrationResult = clientSocket.recv(1024).decode()

    # If there is an error 400 or 401 error message is displayed and program terminates
    if registrationResult != '200 Registration successful':
        sys.exit('Error 400 or 401. Terminating program.')

    print()
    print('Registration successful. Ready for messaging!')

    # Enters into a forever loop that continuously receives or send out message to and from the server
    while True:
        events = selectorObject.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


# Function that receives all messages coming from the server, if it receives the Server exiting message it will log
# out the clients too
def incomingMessage(clientSocket, mask):
    incomeData = clientSocket.recv(1024).decode()

    # Handles receiving the file is there is a incoming file from the server
    if 'Receiving file' in incomeData:
        # Receives all information relating to the file
        fileName = clientSocket.recv(1024).decode()
        sender = clientSocket.recv(1024).decode()
        contentLengthBytes = clientSocket.recv(1024).decode()

        fileLength = int(contentLengthBytes[16:])

        # Opens a new file for writing into
        with open(fileName[15:], 'wb') as f:
            for i in range(0, fileLength, 1024):
                f.write(clientSocket.recv(1024))

        print(fileName)
        print(sender)
        print(f'Content-Length: {contentLengthBytes}')

    elif incomeData != 'DISCONNECT CHAT/1.0':
        print(incomeData)

    else:
        sys.exit('Disconnected from server ... exiting!')


# Function that takes standard input and send it over to the server
def outgoingMessage(stdin, mask):
    userInput = stdin.readline()
    clientSocket.sendall(('@' + userName + ': ' + userInput).encode())

    # Handles attaching the file to be sent over the server
    if '!attach' in userInput:
        # Extracts file information to be sent to the server
        fileData = userInput.split()
        fileName = fileData[1]

        # Open the file that is going to be sent and read the entire file content
        with open(fileName, 'rb') as f:
            fileContents = f.read()

        # Notifies the user of success
        print(f'Attachment {fileName} is sent to server')

        # Sends file length information
        clientSocket.sendall(f'Content-Length: {len(fileContents)}'.encode())

        # Send the file over to the server chunk by chunk
        for i in range(0, len(fileContents), 1024):
            clientSocket.sendall(fileContents[i:i+1024])
    print()


# Special signal handler that detects Ctrl-C and prints error message before terminating program
def handler(incomingSignal, frame):
    print('Interrupt received, shutting down ...')
    clientSocket.sendall(f'DISCONNECT {userName} CHAT/1.0'.encode())
    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv)
