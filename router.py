#!/usr/bin/env python3

import socket
import json
import threading
import time
import sys
import select
import os

# Determina o diretório do código atual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 3:
    # Obtém o caminho do arquivo passado na linha de comando
    startup_file = os.path.abspath(sys.argv[3])

    # Resolve o caminho relativo ao diretório do script router.py
    startup_file = os.path.join(BASE_DIR, startup_file)

    # Verifica se o arquivo existe após o ajuste
    if not os.path.exists(startup_file):
        print(f"Erro: Arquivo de comandos '{startup_file}' não encontrado.")
        sys.exit(1)

    # Atualiza o argumento com o caminho absoluto
    sys.argv[3] = startup_file

# Constantes
PORT = 55151
MAX_COST = 120  # Custo máximo das rotas
TTL = 160  # Time to live

# Estrutura da tabela de roteamento
table_lock = threading.RLock()
routing_table = {}  # {destination: {'next_hop': str, 'distance': int}}
neighbors = set()
deleted_neighbors = set()
running = True
local_ip = ""
period = 0
routers_timers = {}  # {neighbor_ip: last_update_time}

# (Resto do código continua como você forneceu...)

def load_startup_commands(filename):
    import os
    if not os.path.exists(filename):
        print(f"Erro: Arquivo {filename} não encontrado!")
        return
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):  # Ignora linhas vazias ou comentários
                    continue
                command = line.split()
                if len(command) < 3 or command[0] != "add":  # Verifica o formato esperado
                    print(f"Erro: Linha inválida no arquivo - '{line}'")
                    continue
                ip, weight = command[1], int(command[2])
                neighbors.add(ip)
                with table_lock:
                    routing_table[ip] = {'next_hop': ip, 'distance': weight}
    except Exception as e:
        print(f"Erro ao carregar comandos do arquivo: {e}")




def update_timer(ip):
    """Atualiza o timer de um roteador."""
    with table_lock:
        routers_timers[ip] = time.time()

def check_for_dead_links():
    """Verifica se algum roteador parou de enviar atualizações."""
    current_time = time.time()
    with table_lock:
        for ip in list(routers_timers.keys()):
            if abs(current_time - routers_timers[ip]) > 4 * period:  # Período de expiração
                routers_timers.pop(ip, None)
                remove_routes_from_router(ip)

def remove_routes_from_router(ip):
    """Remove todas as rotas aprendidas de um vizinho."""
    global routing_table
    with table_lock:
        if ip in neighbors:
            neighbors.discard(ip)
            routing_table = {
                dest: route for dest, route in routing_table.items() if route["next_hop"] != ip
            }
        else:
            routing_table = {
                dest: route for dest, route in routing_table.items() if dest != ip
            }
def process_update(src_ip, message):
    """Processa mensagens de atualização de tabela."""
    distances = message.get('distances', {})
    for destination, custo_extra in distances.items(): #distance.items par chave fechadura com o ip do roteador e a distancia até ele
        update_timer(destination) #atualiza o timer de todos os destinos da mensagem de update
        
        if destination == local_ip:
            continue  # Não altera a distância do próprio roteador
        merge_route(src_ip, destination, custo_extra)


def send_message(dest_ip, message):
    """Envia mensagem UDP para um destino."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = json.dumps(message, indent=4).encode('utf-8')
        sock.sendto(data, (dest_ip, PORT))
        sock.close()
    except Exception as e:
        print(f"Erro ao enviar mensagem para {dest_ip}: {e}")

def receive_message(sock):
    """Recebe mensagens UDP e processa os dados."""
    global routing_table, neighbors
    while running:
        try:
            data, addr = sock.recvfrom(1024)
            message = json.loads(data.decode('utf-8'))
            src_ip = message["source"]


            if message['type'] == 'update':
                process_update(src_ip, message)
            elif message['type'] == 'data':
                process_data(message)
            elif message['type'] == 'trace':
                process_trace(src_ip, message)
        except socket.timeout:
            pass
        except Exception as e:
            if running:
                print(f"Erro ao receber mensagem: {e}")

def merge_route(next_hop, destination, custo):
    """Atualiza ou insere uma rota na tabela de roteamento."""
    if destination == local_ip:
        return  # Ignora tentativas de atualizar a métrica para o próprio roteador

    with table_lock:
        # Verifica se o next_hop está na tabela
        if next_hop not in routing_table:
            routing_table[next_hop] = {'next_hop': next_hop, 'distance': custo}

        if destination in routing_table:
            route = routing_table[destination]
        
            # Verifica se encontrou uma rota melhor ou se a métrica mudou
            if custo < route['distance']:
                route['next_hop'] = next_hop
                route['distance'] = custo
        else:
            # Nova rota
            routing_table[destination] = {
                'next_hop': next_hop,
                'distance': custo
            }


def process_data(message):
    """Processa mensagens de dados."""
    if message['destination'] == local_ip:
        print("Payload recebido:", json.dumps(message['payload'], indent=4))
    else:
        with table_lock:
            if message['destination'] in routing_table:
                send_message(routing_table[message['destination']]['next_hop'], message)

def process_trace(src_ip, message):
    """Processa mensagens de trace."""
    
    # Evita loops: Se o IP atual já está na lista de roteadores, descarta a mensagem
    if local_ip in message["routers"]:
        print(f"Loop detectado no trace. Descartando mensagem.")
        return

    # Adiciona o IP do roteador atual à lista de roteadores
    message["routers"].append(local_ip)

    if message["destination"] == local_ip:
        # Se o roteador atual for o destino, cria uma mensagem de resposta
        response = {
            "type": "data",
            "source": local_ip,
            "destination": message["source"],
            "payload": json.dumps(message)  # O trace completo como payload
        }
        
        send_message(message["source"], response)
    else:
        # Encaminha a mensagem ao próximo salto
        with table_lock:
            if message["destination"] in routing_table:
                next_hop = routing_table[message["destination"]]["next_hop"]
                send_message(next_hop, message)
            else:
                print(f"Destino {message['destination']} inalcançável. Trace descartado.")

def send_periodic_updates():
    """Envia atualizações periódicas para os vizinhos."""
    while running:
        time.sleep(period)
        check_for_dead_links() 
        with table_lock:
            for neighbor in neighbors:
                # Gera a tabela de atualização com Split Horizon
                if neighbor in routing_table:
                    distance_to_add = routing_table[neighbor]['distance']  # Distância até o vizinho

                distances = {}
                for dest, route in routing_table.items():
                    if route["next_hop"] == neighbor:
                        # Evita enviar rotas aprendidas de um vizinho de volta para ele (Split Horizon)
                        continue

                    # Verifica se a rota é a melhor disponível
                    if dest in distances:
                        # Se já existe uma entrada para o destino, escolhe a melhor
                        current_cost = distances[dest]
                        new_cost = route["distance"] + (distance_to_add if dest != neighbor else 0)
                        if new_cost < current_cost:
                            distances[dest] = new_cost
                    else:
                        # Caso contrário, adiciona a rota atual
                        distances[dest] = route["distance"] + (distance_to_add if dest != neighbor else 0)

                # Monta a mensagem de atualização
                update_message = {
                    "type": "update",
                    "source": local_ip,
                    "destination": neighbor,
                    "distances": distances
                }

                # Imprime a mensagem de atualização

                # Envia atualização para o vizinho
                send_message(neighbor, update_message)

def handle_commands():
    """Interface de comando para o usuário."""
    global running
    while running:
        try:
            command = input().strip()
            parts = command.split()
            if not parts:
                continue

            if parts[0] == "add" and len(parts) == 3:
                ip, weight = parts[1], int(parts[2])
                neighbors.add(ip)

                if ip in deleted_neighbors:
                    deleted_neighbors.remove(ip)
                    

                with table_lock:
                    routing_table[ip] = {'next_hop': ip, 'distance': weight}

            elif parts[0] == "del" and len(parts) == 2:
                ip = parts[1]
                with table_lock:
                    # Remove o vizinho da tabela de roteamento
                    neighbors.discard(ip)
                    if ip in routing_table:
                        del routing_table[ip]
                    
                    # Remove rotas aprendidas através do vizinho
                    to_remove = [dest for dest, route in routing_table.items() if route["next_hop"] == ip]
                    for dest in to_remove:
                        del routing_table[dest]

                    deleted_neighbors.add(ip)  # Adiciona o vizinho ao conjunto de roteadores deletados
                


            elif parts[0] == "trace" and len(parts) == 2:
                destination = parts[1]
                trace_message = {
                    "type": "trace",
                    "source": local_ip,
                    "destination": destination,
                    "routers": [local_ip]  # Inicia a lista com o roteador atual
                }
                with table_lock:
                    if destination in routing_table:
                        next_hop = routing_table[destination]["next_hop"]
                        send_message(next_hop, trace_message)
                    else:
                        print(f"Rota para {destination} desconhecida. Trace não enviado.")

            elif parts[0] == "quit":
                shutdown()
        except EOFError:
            shutdown()


def shutdown():
    """Encerramento seguro."""
    global running
    running = False
    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join()
def main():
    global local_ip, period, running

    if len(sys.argv) < 3:
        print("Uso: python3 router.py <endereco> <periodo> [arquivo de comandos]")
        return

    local_ip = sys.argv[1]
    period = int(sys.argv[2])
    startup_file = sys.argv[3] if len(sys.argv) > 3 else None

    if startup_file:
        # Resolve o caminho relativo em relação ao diretório base
        startup_file = os.path.join(BASE_DIR, startup_file)

    # Configuração do socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((local_ip, PORT))
    sock.settimeout(1)


    # Inicializa a tabela de roteamento
    routing_table[local_ip] = {'next_hop': local_ip, 'distance': 0}
    

    # Carrega comandos do arquivo de startup
    if startup_file:
        load_startup_commands(startup_file)

    # Threads de comunicação
  
    receiver_thread = threading.Thread(target=receive_message, args=(sock,))
    update_thread = threading.Thread(target=send_periodic_updates)

    receiver_thread.start()
    update_thread.start()

   
    try:
        handle_commands()  # Modo interativo
    except KeyboardInterrupt:
        shutdown()

    running = False
    sock.close()
    receiver_thread.join()
    update_thread.join()




if __name__ == "__main__":
    main() 