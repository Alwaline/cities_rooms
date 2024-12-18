import socket
from threading import Thread, Event, Timer
import pickle
import time

class Player:
    def __init__(self, name, conn, curr_room=None):
        self.name = name
        self.conn : socket.socket = conn
        self.curr_room = curr_room

class Room(Thread):
    def __init__(self, server, number):
        super().__init__()
        self.server : Server = server
        self.number = number
        self.players : list [Player] = []
        self.words = []
        self.game_start = Event()

    def add_player(self, conn):
        self.server.send(conn, f'Введите имя')
        data = self.server.recv(conn)
        if data:
            name = data
            self.players.append(Player(name, conn, self))
            self.server.send(conn, f'Вы успешно подключились к комнате {self.number}')

    def rem_player(self, player):
        self.players.remove(player)

    
    def view(self) -> str: 
        return f'{self.number}. Комната {self.number}; количество игроков: {len(self.players)}'
    
    def is_full(self):
        return len(self.players) >= 2
    
    def exit(self, player):
        self.rem_player(player)
    
    def refresh(self):
        if not self.game_start.is_set():
            self.game_start.set()

        for player in self.players:
            self.rem_player(player)

    def lose(self, player):
        self.game_start.set()
        self.notify(f'Игрок {player.name} проиграл')
        
    def kick_player(self, player):
        self.exit(player)
        self.refresh()
        self.server.disconect_client(player.conn, 'Уходи')

    def change(self, player):
        self.rem_player(player)
        conn = player.conn
        self.server.change_room(conn)
        

    def check_data(self, data):
        word = data.strip().lower()
        if word == '/exit':
            return -1, ''
        elif word == '/change':
            return -2, ''
        elif word in self.words:
            return 0, f"Город {word} уже вводили"
        elif self.words and word[0] != self.words[-1][-1]:
            return 0, f"Город должен начинаться на букву {self.words[-1][-1]}"
        return 1, ''

    def time_out(self, player):
        self.lose(player)
        self.change(player)
        self.exit_another()

    def run(self):
        while True:
            self.words = []
            self.game_start.clear()
            while not self.is_full():
                time.sleep(1)
                
            message = f'Игра в комнате {self.number} началась. Первый ходит {self.players[0].name}'
            self.notify(message)

            player_step = 0
            curr_player = self.players[player_step]
            while not self.game_start.is_set():
                timer = Timer(15.0, self.time_out, (curr_player,))
                timer.start()
                data = self.server.recv(curr_player.conn)
                if data:
                    status, message = self.check_data(data)
                    match status:
                        case 1:
                            message = f'{curr_player.name} : {data.strip().lower()}'
                            self.notify(message, curr_player.conn)
                            self.words.append(data.strip().lower())
                            player_step = 0 if player_step else 1
                            curr_player = self.players[player_step]
                            timer.cancel()
                        case 0:
                            self.server.send(curr_player.conn, message)
                        case -1:
                            self.lose(curr_player)
                            self.exit(curr_player)
                            self.exit_another()
                            timer.cancel()
                        case -2:
                            self.lose(curr_player)
                            self.change(curr_player)
                            self.exit_another()
                            timer.cancel()
            else:
                self.refresh()

    def exit_another(self):
        curr_player = self.players[0]
        self.change(curr_player)
                
    def notify(self, message, conn=None):
        for player in self.players:
            if player.conn is not None and player.conn != conn:
                self.server.send(player.conn, message)
        
        
        
class Server(Thread):
    EOF = b'///'
    BUFFER_SIZE = 1024

    def __init__(self, address):
        super().__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # STREAM TCP/ DGRAM UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print('Socket created')
        self.sock.bind(address)
        print('Socket binded')
        self.sock.listen(2)
        print('Socket now listening')
        self.clients = set()
        self.clients_name = dict()
        self.rooms = []


    def __del__(self):
        self.sock.close()


    def create_rooms(self, count=4):
        for i in range(count):
            self.rooms.append(Room(self, i+1))

        for room in self.rooms:
            room.start()


    def select_room(self, conn):
        data = self.recv(conn)
        if data:
            if data == '/exit':
                return 0, 'До свидания!'
            room = int(data)
            if room not in range(1,5):
                return -1, f'Выберите комнату 1-4'
            elif self.rooms[room-1].is_full():
                return -1, f'Комната {room} заполнена, выберите другую'
            else: return room, f''

    def handle_client(self, conn):
        message = 'Вы успешно подключились к серверу. \n Пожалуйста выберите комнату:'
        self.send(conn, message)
        
        self.change_room(conn)

    def change_room(self, conn):
        self.print_rooms(conn)
        select, message = self.select_room(conn)
        while select < 0:
            self.send(conn, message)
            self.print_rooms(conn)
            select, message = self.select_room(conn)
        
        if select > 0:
            self.rooms[select-1].add_player(conn)
        else:
            message = f'Досвидания!'
            self.disconect_client(conn, message)

    def disconect_client(self, conn, message):
        message = f'Вы были отключены с сообщением: {message}'
        self.send(conn, message)
        conn.close()
        self.clients.remove(conn)

    def print_rooms(self, conn):
        self.send(conn, f'/exit - для выхода')
        for room in self.rooms:
            time.sleep(0.1)
            self.send(conn, room.view())


    def run(self):
        self.create_rooms()

        while True:
            client_sock, client_address = self.sock.accept()
            print(client_sock, client_address)
            self.clients.add(client_sock)
            Thread(target=self.handle_client, args=(client_sock,)).start()

    def send(self, conn: socket.socket, data: str):
        serialized_data = pickle.dumps(data)
        conn.send(serialized_data)
        conn.send(Server.EOF)

    def recv(self, conn: socket.socket) -> bytearray:
        result = bytearray()
        while True:
            data: bytes = conn.recv(Server.BUFFER_SIZE)
            result.extend(data)
            if not data:
                break
            if result[-3:] == Server.EOF:
                break
        return pickle.loads(result[:-3])


address = ('localhost', 9000)
server = Server(address)
server.start()
server.join()
''