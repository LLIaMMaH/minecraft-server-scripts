tmux new -s MCS -c /server/GTNH-TST-273/ -d

tmux send-keys -t MCS:1 './start.sh' Enter
