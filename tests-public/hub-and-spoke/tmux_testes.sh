#!/bin/sh
set -eu

exe="../../router.py"

# Inicia o primeiro terminal com o comando para o hub
tmux split-pane -h "python3 $exe 127.0.1.10 10" &

# Aguarda para garantir que o primeiro comando seja executado antes de iniciar os outros
sleep 1

# Envia os comandos do arquivo hub.txt no primeiro terminal
while IFS= read -r line; do
    tmux send-keys "$line" C-m
    sleep 0.5  # Dá tempo para o comando ser processado antes de enviar o próximo
done < hub.txt

# Para cada "spoke", inicia uma nova janela e envia os comandos do arquivo spoke.txt
for i in $(seq 1 5); do
    tmux split-pane -h "python3 $exe 127.0.1.$i 10" &
    tmux select-layout even-horizontal

    # Envia os comandos do arquivo spoke.txt para o terminal correspondente
    while IFS= read -r line; do
        tmux send-keys "$line" C-m
        sleep 0.5  # Dá tempo para o comando ser processado antes de enviar o próximo
    done < spoke.txt
done
