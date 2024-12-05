import socket
from threading import Thread, Timer, Event
import pickle
import time

class Client:
    EOF = b'///'
    BUFFER_SIZE = 1024

    def __init__(self, address):
        super().__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # STREAM TCP/ DGRAM UDP
        print('Connecting to {}:{}'.format(*address))
        self.sock.connect(address)
        print('Connected to server')
        self.is_active = Event()
        self.communicate()
        
    def receive_messages(self):
        while not self.is_active.is_set():
            data = self.recv()
            if not data: break
            print(data)

    def send_messages(self):
        message = ""
        while message != '/exit':
            message = input()
            self.send(message)
        else:
            self.is_active.set()
        self.sock.close()

    def communicate(self):
        thread_recv = Thread(target=self.receive_messages)
        thread_send = Thread(target=self.send_messages)
        thread_recv.start()
        thread_send.start()

    def send(self, data: str):
        serialized_data = pickle.dumps(data)
        self.sock.send(serialized_data)
        self.sock.send(Client.EOF)

    def recv(self) -> bytearray:
        result = bytearray()
        while True:
            data: bytes = self.sock.recv(Client.BUFFER_SIZE)
            result.extend(data)
            if not data:
                break
            if result[-3:] == Client.EOF:
                break
        return pickle.loads(result[:-3])



address = ('localhost', 9000)
client = Client(address)