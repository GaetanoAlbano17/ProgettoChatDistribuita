import re
import time
import threading
import socket
import sys
import os
import json
from random import choice

import keyboard


class Chat:

    def __init__(self):
        """
        Costruttore della classe Chat, che comprende tutto il codice e i vari metodi per il protocollo di comunicazione.
        Inizializziamo tutte le variabili di tipo globale che utilizzeremo per il salvataggio delle varie informazioni tra i vari client, come l'username, le porte, gli Ip ecc.
        """
        self.start_port = 8550
        self.end_port = 8560
        self.socket_server = None
        self.client_conn = None
        self.server_conn = [None, None]
        self.inter_conn = [None, None]
        self.inter_ports = [None, None]
        self.inter_usernames = ["", ""]
        self.chatting = False
        self.waiting_for_acceptance = False
        self.is_bridge = False
        self.username = "Default"
        self.neighbor_username = ""
        self.contacts = {}
        self.neighbor_contacts = {}
        self.port = self.choose_port()
        self.addr = ['localhost', self.port]
        self.client_addr = ['localhost', None]
        self.server_conf()

    def is_port_in_use(self, port):
        """
        Metodo utilizzato per verificare che una porta, all'interno del range utilizzato, sia già stata utilizzata o no.
        Se è libera, possiamo assegnarle un client.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = False
        try:
            sock.bind(("localhost", port))
            result = True
        except:
            print()
        sock.close()
        return not result

    def choose_port(self):
        """
        Mi da la possibilità, andando a richiamare il metodo is_port_in_use, di capire quale porta sia in uso o no
        """
        ports = range(self.start_port, self.end_port)
        for port in ports:
            if not self.is_port_in_use(port):
                return port
        return 0

    def server_conf(self):
        """
        E' un metodo utilizzato per definire la comunicazione di quel client.
        Ci dice che il client è in ascolto nella porta trovata libera
        """
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_server.bind((self.addr[0], self.addr[1]))
        self.socket_server.listen(1)
        print(":: In ascolto sulla porta {}".format(str(self.addr[1])))

    def simple_connection(self, conn_id, message):
        """
        Metodo simile a quello successivo, ovvero 'connect_as_client', ma verrà utilizzato prioritariamente per i messaggi broadcast.
        Si vuole qui una connessione più veloce rispetto al metodo connect_as_client in quanto in quell'altro ci sono dei controlli in più o dei messaggi che a noi non servono.
        Quindi questo metodo, come il successivo, sarà utile nella connessione ad un altro dispositivo. Vengono gestiti anche possibili errori.
        """
        try:
            # conn_id è una porta
            conn_id = int(conn_id)
        except ValueError:
            # conn_id è un username
            for port, username in self.contacts.items():
                if username == conn_id:
                    conn_id = port
                    break
        self.client_addr[1] = conn_id
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('localhost', self.client_addr[1]))
            sock.sendall(message.encode())
            sock.close()
        except Exception as e:
            print("Impossibile comunicare con {}: {}".format(self.client_addr[1], str(e)))

    def connect_as_client(self, conn_id, message, bridge, position):
        """
        Metodo utilizzato prioritariamente per la messaggistica tra due nodi.
        Ci sono più messaggi e il metodo sarà utile per la connessione ad un altro dispositivo.
        La connessione viene salvata nella variabile inter_conn. Vengono gestiti anche gli errori.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Converti conn_id in una porta valida
        # Se è un bridge, le porte sono già in self.inter_ports
        if not bridge:
            try:
                # conn_id è una porta
                conn_id = int(conn_id)
            except ValueError:
                # conn_id è un username
                for port, username in self.contacts.items():
                    if username == conn_id:
                        conn_id = port
                        break
            self.client_addr[1] = conn_id

        # Connetti uno o due client a seconda che sia un bridge (intermediario)
        if bridge:
            # Tentativo persistente di connessione al client
            while sock.connect_ex(('localhost', self.inter_ports[position])) != 0:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print("Connessione in corso al client...")
                time.sleep(2)

            # Salva la nuova connessione
            self.inter_conn[position] = sock
        else:
            try:
                sock.connect(('localhost', self.client_addr[1]))
                self.client_conn = sock
            except Exception as e:
                print("L'utente non è disponibile")
                return

        # Invia il messaggio al client
        try:
            if bridge:
                self.inter_conn[position].sendall(message.encode())
            else:
                self.client_conn.sendall(message.encode())
        except Exception as e:
            if bridge:
                if position == 0:
                    print("Errore nell'invio del messaggio al client di origine")
                else:
                    print("Errore nell'invio del messaggio al client di destinazione")
            else:
                print("Errore nell'invio del messaggio al client")

    def wait_as_server(self, hideMessage=False):
        """
        Metodo che dice di aspettare un qualcuno che comunica qualcosa. Ci sono tante funzioni utilizzate, e pare come se sia il client.
        Esempio se la risposta è broadcast vengono fate varie opzioni ecc. Sono utilizzate le varie funzioni per dividere le varie cose.
        Esempio anche la presenza di @friend che infatti sarà utile per una richiesta di amicizia.
        Esempio del @disconnectfriends invece, in cui appena arriva un messaggio di questo tipo, viene cancellato tra i contatti l'username aggiunto e dice che
        il nodo è rimosso dai contatti.
        Esempio del @request ci da le informazioni dei nodi aggiunti, tipo username e porta e viene salvato all'interno della nostra variabile per i contatti.
        E' un metodo per la sincronizzazione della comunicazione nei messaggi, per far sì che nel momento in cui qualcuno invia, l'altro diventa server e viceversa.
        Vengono passate variabili che dicono che in un certo momento si sta accettando, si smette di accettare o altro.
        Infatti, alla fine, la variabile waiting_for_acceptance = False
        """
        try:
            new_client, _ = self.socket_server.accept()
        except:
            sys.exit(0)

        response = new_client.recv(1024).decode("utf-8")
        try:
            # print("Ricevuto: {}".format(response))
            if self.server_conn[0] is None:
                self.server_conn[0] = new_client
            else:
                self.server_conn[1] = new_client

            if (response.startswith("@broadcast")):
                hideMessage = True
                response = response.replace("@broadcast ", "")
                nome = str(response.split(" ")[0])
                messaggio = response.replace(nome, "")
                print("[B] {} »{}".format(nome, messaggio))
            elif (response.startswith("@disconnectFriends")):
                response = response.split(" ", 3)
                hideMessage = True

                port = int(response[1])
                username = response[2]

                if port in self.contacts.keys():
                    del self.contacts[port]
                    print(":: {} si è disconnesso ed è stato rimosso tra i tuoi contatti".format(username))
                else:
                    print(":: {} non è presente tra i tuoi contatti".format(username))
            else:
                response = response.split(" ", 3)

                if response[0] == '@friend':
                    hideMessage = True

                    self.client_addr[1] = int(response[1])
                    self.neighbor_username = response[2]

                    self.contacts[self.client_addr[1]] = self.neighbor_username
                    self.neighbor_contacts = json.loads(response[3])

                    if self.neighbor_contacts.get(str(self.addr[1]), None) is not None:
                        del self.neighbor_contacts[str(self.addr[1])]

                    print(":: {} è stato aggiunto tra i tuoi contatti".format(self.neighbor_username))
                    message = "@acceptRequest {} {} {}".format(self.addr[1], self.username, json.dumps(self.contacts))
                    self.simple_connection(self.client_addr[1], message)
                elif response[0] == '@acceptRequest':
                    hideMessage = True

                    self.client_addr[1] = int(response[1])
                    self.neighbor_username = response[2]

                    self.contacts[self.client_addr[1]] = self.neighbor_username
                    self.neighbor_contacts = json.loads(response[3])

                    if self.neighbor_contacts.get(str(self.addr[1]), None) is not None:
                        del self.neighbor_contacts[str(self.addr[1])]

                    print(":: {} è stato aggiunto tra i tuoi contatti".format(self.neighbor_username))
                else:
                    if response[0] == '@inter_accepted':
                        return
                    if response[0] == '@bridge':
                        print("Richiesta di server ricevuta")

                        self.inter_ports[0] = int(response[2])
                        self.inter_ports[1] = int(response[3])
                        self.inter_usernames[0] = response[1]
                        self.inter_usernames[1] = self.contacts[self.inter_ports[1]]

                        message = "@intermediario {} {}".format(self.addr[1], self.inter_usernames[0])
                        self.connect_as_client(None, message, True, 1)
                        self.wait_as_server()

                        message = "@bridge_accepted {} {}".format(self.addr[1], self.inter_usernames[1])
                        self.connect_as_client(None, message, True, 0)

                        print("Richiesta di server accettata. Ora sono un server")
                        self.is_bridge = True
                        threading.Thread(target=self.listen, args=(
                        self.server_conn[0], self.inter_conn[1], self.inter_usernames[0],)).start()
                        threading.Thread(target=self.listen, args=(
                        self.server_conn[1], self.inter_conn[0], self.inter_usernames[1],)).start()
                        return
                    else:
                        self.client_addr[1] = int(response[1])
                        self.neighbor_username = response[2]
                        if response[0] == '@bridge_accepted':
                            pass
                        elif response[0] == '@intermediario':
                            print(":: Sincronizzazione sulla porta intermediario {}".format(self.client_addr[1]))
                            message = "@inter_accepted"
                            self.connect_as_client(self.client_addr[1], message, False, None)
                        elif response[0] == '@request' or response[0] == '@accept':
                            self.contacts[self.client_addr[1]] = self.neighbor_username
                            self.neighbor_contacts = json.loads(response[3])

                            if self.neighbor_contacts.get(str(self.addr[1]), None) is not None:
                                del self.neighbor_contacts[str(self.addr[1])]

                            if self.waiting_for_acceptance:
                                print("Connessione accettata. Ora siete collegati.")
                            elif not self.chatting:
                                print(":: Sincronizzazione sulla porta {}".format(self.client_addr[1]))
                                message = "@accept {} {} {}".format(self.addr[1], self.username,
                                                                    json.dumps(self.contacts))
                                self.connect_as_client(self.client_addr[1], message, False, None)
        except Exception as e:
            print(str(e))
            return

        self.chatting = True
        self.waiting_for_acceptance = False
        if not hideMessage:
            if self.client_addr[1] in self.contacts:
                nome = self.contacts[self.client_addr[1]]
            else:
                nome = self.client_addr[1]
            print("Chat stabilita con: {}, @termina per chiudere la chat".format(nome))
            self.listen(self.server_conn[0], None, self.neighbor_username, hideMessage)
        else:
            self.restart_connections("", hideMessage)

    def input_loop(self):
        """
        Metodo in cui vengono difiniti i comandi, le opzioni ecc.
        """
        while (self.username == "Default"):
            print(":: Cambia il tuo nickname come @nick NOME")
            comando = input()
            if comando.startswith("@nick"):
                if not self.chatting:
                    self.username = comando.split(" ")[1]
                    print(":: Il nome utente è stato cambiato in {}".format(self.username))
                else:
                    print(":: Impossibile cambiare il nome utente durante la conversazione")

        print("\n:: Pronto a ricevere comandi o messaggi")
        print("\n--- COMANDI ---\n" +
              "▪ Aggiungi nuovo contatto: @add PORTA\n" +
              "▪ Crea una chat privata: @msg NOME\n" +
              "▪ Messaggio di broadcast a tutti i contatti: @broadcast MESSAGGIO\n" +
              "▪ Lista dei contatti: @contatti\n" +
              "▪ Disconnetti: @disconnect")
        while True:
            comando = input()
            if comando.startswith("@contatti"):
                if not self.chatting:
                    if len(self.contacts) == 0:
                        print(":: Non ci sono contatti in rubrica.")
                    else:
                        for key, value in self.contacts.items():
                            print("{} : {}".format(value, key))
                else:
                    print(":: Impossibile visualizzare i contatti durante la conversazione.")
            elif comando.startswith("@add"):
                if len(comando.split()) > 1:
                    if not self.chatting:
                        id_conn = comando.split(" ")[1]
                        message = "@friend {} {} {}".format(self.addr[1], self.username, json.dumps(self.contacts))
                        self.send_friend_request(id_conn, message)
                    else:
                        print(":: Hai una chat attiva. Scrivi @termina per terminare la conversazione.")
                else:
                    print(":: Inserisci la porta dell'utente da aggiungere.")
            elif comando.startswith("@msg"):
                if len(comando.split()) > 1:
                    if not self.chatting:
                        id_conn = comando.split(" ")[1]
                        print("Connessione in corso...")
                        message = "@request {} {} {}".format(self.addr[1], self.username, json.dumps(self.contacts))
                        self.waiting_for_acceptance = True
                        self.connect_as_client(id_conn, message, False, None)
                    else:
                        print(":: Hai già una chat attiva. Scrivi @termina per terminare la conversazione.")
                else:
                    print(":: Inserisci il nome dell'utente per poter messaggiare.")
            elif comando.startswith("@broadcast"):
                if len(comando.split()) > 1:
                    if not self.chatting:
                        message = comando.replace("@broadcast ", "")
                        self.send_broadcast_message(message)
                    else:
                        print(":: Hai una chat attiva. Scrivi @termina per terminare la conversazione.")
                else:
                    print(":: Inserisci il messaggio da inviare in broadcast.")
            elif comando.startswith("@termina"):
                if not self.chatting:
                    print(":: Nessuna connessione attiva")
                    continue
                message = ":: Sei uscito dalla conversazione"
                self.restart_connections(message)

            elif comando.startswith("@disconnect"):
                self.close_connections(True)
                break

            elif comando.startswith("@"):
                print("\n--- COMANDI ---\n" +
                      "▪ Aggiungi nuovo contatto: @add PORTA\n" +
                      "▪ Crea una chat privata: @msg NOME\n" +
                      "▪ Messaggio di broadcast a tutti i contatti: @broadcast MESSAGGIO\n" +
                      "▪ Lista dei contatti: @contatti\n" +
                      "▪ Disconnetti: @disconnect")
            else:
                if not self.chatting:
                    print(":: Non hai una conversazione aperta")
                elif self.waiting_for_acceptance:
                    print(":: Aspetta una risposta")
                else:
                    self.client_conn.sendall(comando.encode())

    def close_connections(self, exit, friends=False):
        """
        Metodo per chiudere la connessione. Ci sono tante funzioni per chiudere una connessione in tutti i casi.
        Ovviamente, alla fine, verranno resettate le variabili per far ripartire il programma.
        La porta ritorna così disponibile.
        """
        # Prima avvertiamo i nostri client e poi disconnettiamo tutto
        try:
            if self.is_bridge:
                # Se la connessione è una bridge, invia un messaggio di terminazione ai client connessi alla bridge
                self.inter_conn[0].sendall("@termina".encode())
                self.inter_conn[1].sendall("@termina".encode())
                self.inter_conn[0].close()
                self.inter_conn[1].close()
                self.server_conn[0].close()
                self.server_conn[1].close()
            else:
                if self.chatting or friends:
                    # Se si sta chattando o friends=True, invia un messaggio di terminazione al client connesso
                    self.client_conn.sendall("@termina".encode())
                    self.client_conn.close()
                    self.server_conn[0].close()
                else:
                    if self.client_conn is not None and self.server_conn[0] is not None:
                        # Altrimenti, se ci sono una connessione client e una connessione server attive, vengono chiuse
                        self.client_conn.close()
                        self.server_conn[0].close()
        except Exception as e:
            pass
            # print("Errore durante la disconnessione", e)

        if exit:
            # Se exit=True, invia un messaggio di disconnessione agli amici e chiudi il server
            message = "@disconnectFriends {} {}".format(self.addr[1], self.username)
            self.remove_friend_request(message)
            self.socket_server.close()
            sys.exit(0)
        # Resetta le variabili per far ripartire il programma
        self.server_conn = [None, None]
        self.inter_conn = [None, None]
        self.inter_ports = [None, None]
        self.inter_usernames = ["", ""]
        self.client_addr[1] = None
        self.client_conn = None
        self.neighbor_username = ""
        self.neighbor_contacts = {}
        self.is_bridge = False
        self.chatting = False
        self.waiting_for_acceptance = False

    def listen(self, origin, dest, origin_username, hideMessage=False):
        """
        Metodo utilizzato per la ricezione dei messaggi, soprattutto appena si avvia la chat.
        """
        while True:
            info = None #inizializziamo info come None e poi successivamente proviamo a ricevere dati con 'origin'
            try:
                info = origin.recv(64).decode("utf-8")
            except Exception as e:
                break

            # print("Ricevuto: ", info)
            if len(info) == 0: #significa che non son stati ricevuti dati
                if self.is_bridge:#se l'istanza è un ponte viene mandato un errore
                    print("errore: nessun dato da leggere da uno dei clienti")
                    dest.sendall("@termina".encode()) #invio messaggio al destinatario
                    message = ":: {} ha chiuso la conversazione.".format(self.neighbor_username)
                    self.restart_connections(message, hideMessage)
                    break

                else:
                    if not hideMessage: #se hideMessage è falso stampo un errore
                        print("Si è verificato un errore nella connessione, alla ricerca di un intermediario...")
                    bridge_port = self.get_bridge_port()
                    if bridge_port is None: #se succede questo si crea un mex di chiusura delle connessioni
                        message = "Il vicino non ha contatti utilizzabili come intermediari, chiusura delle connessioni..."
                        self.restart_connections(message, hideMessage)
                        break

                    message = "@bridge {} {} {}".format(self.username, self.addr[1], self.client_addr[1])
                    # Si salvano gli attributi che non devono essere cancellati
                    neighbor_username = self.neighbor_username
                    neighbor_contacts = self.neighbor_contacts
                    self.close_connections(False)

                    self.waiting_for_acceptance = True
                    self.neighbor_username = neighbor_username
                    self.neighbor_contacts = neighbor_contacts

                    print("Porta scelta come intermediario: ", bridge_port)
                    self.connect_as_client(bridge_port, message, False, None)
                    threading.Thread(target=self.wait_as_server).start()
                break

            if info.startswith("@termina"): #se il mex inizia con @termina viene controllato se l'istanza corrente è un ponte
                if self.is_bridge: #se è un ponte viene inviato un messaggio di chiusura e si riavviano le connessioni
                    dest.sendall("@termina".encode())
                message = ":: {} ha chiuso la conversazione.".format(self.neighbor_username)
                self.restart_connections(message)
                break

            print("{} » {}".format(origin_username, info))
            if self.is_bridge:
                dest.sendall(info.encode())

    def send_broadcast_message(self, message):
        """
        Metodo per i messaggi broadcast. Viene fatto un controllo sulla rubrica,e, se ci sono, si utilizza simple_connection, e ci si connette con un ciclo for a tutti i contatti
        e invia di conseguenza il messaggio.
        """
        if len(self.contacts) == 0:
            print("Nessun contatto disponibile per inviare il messaggio di broadcast.")
            return
        message = "@broadcast {} {}".format(self.username, message)
        for port in self.contacts.keys():
            self.simple_connection(port, message)
        print("Messaggio di broadcast inviato a tutti i contatti.")

    def send_friend_request(self, port, message):
        """
         Metodo simile al precedente, fa la stessa cosa.
        """
        if port in self.contacts:
            print("Il contatto è già presente nella tua lista.")
            return
        self.simple_connection(port, message)

    def remove_friend_request(self, message):
        """
        Metodo simile al precedente
        """
        for port in self.contacts.keys():
            self.simple_connection(port, message)

    def get_bridge_port(self):
        """
        Ci da una porta di comunicazione tra i contatti
        """
        if len(self.neighbor_contacts) == 0:
            return None
        return choice(list(self.neighbor_contacts.keys()))

    def restart_connections(self, message, hideMessage=False):
        """
        Metodo per restartare una comunicazione col client senza che avvenga una disconnessione definitiva.
        """
        if not hideMessage:
            print(message)
        self.close_connections(False)
        threading.Thread(target=self.wait_as_server).start()

    def activeChat(self):
        """
        Metodo in cui si attiva il thread di comunicazione con tutti i metodi precedenti
        """
        threading.Thread(target=self.wait_as_server).start()
        self.input_loop()

#Richiamo l'attivazione della Chat
Chat().activeChat()