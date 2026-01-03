#!/bin/bash
if [ ${#VIRTUAL_ENV} -gt 0 ]; then
    deactivate
fi

check_process_id() {
  if [ "$(uname)" == "Darwin" ]; then
    # tips
    echo -e "\033[34m ps -ef |grep \"$1\" |grep -v \"grep\" |awk '{print \$2}' |head -n 1 \033[0m"
    pid=`ps -ef |grep "$1" |grep -v "grep" |awk '{print $2}' |head -n 1`
  else
    # tips
    echo -e "\033[34m ps -aux |grep \"$1\" |grep -v \"grep\" |awk '{print \$2}' |head -n 1 \033[0m"
    pid=`ps -aux |grep "$1" |grep -v "grep" |awk '{print $2}' |head -n 1`
  fi
  # echo "process: $1 / pid: $pid"
  if [ -z $pid ]; then
    pid=0
  fi
}
check_port() {
  if [ "$(uname)" == "Darwin" ]; then
    # tips
    echo -e "\033[34m netstat -anp tcp -v | grep \".$1 \" |awk '{print \$11}' |head -n 1 \033[0m"
    temp=`netstat -anp tcp -v | grep ".$1 " |awk '{print $11}' |head -n 1`
    temp=${temp%/*}
    pid=${temp#*:}
  else
    # tips
    echo -e "\033[34m netstat -tlpn | grep \":$1 \" |grep -v \"grep\" |awk '{print \$7}' |head -n 1 \033[0m"
    temp=`netstat -tlpn | grep ":$1 " |grep -v "grep" |awk '{print $7}' |awk -F '/' '{print $1}' |head -n 1`
    pid=${temp%/*}
  fi
  # echo "port: $1 / pid: $pid"
  if [ -z $pid ]; then
    pid=0
  fi
}

if [ -f '.env' ]; then
  source .env
elif [ -f '.env.sample' ]; then
  source .env.sample
else
  export UVICORN_PORT=8000
fi
if [ -n "$SSL_CERTFILE" ] && [ -f "$SSL_CERTFILE" ] && [ -n "$SSL_KEYFILE" ] && [ -f "$SSL_KEYFILE" ]; then
  export UVICORN_PORT=443
fi
export PROCESS_MAIN='backend/main.py'
export PROCESS_APP='backend/app.py'

ulimit -n 204800

if [ "$1" == "init" ]; then
  cnip=`curl cip.cc |grep '中国' |wc -l`
  if [ $cnip -gt 0 ]; then
    ip=`curl ifconfig.me`
    echo "The current ip: $ip belongs to China"
    pyproxy=' -i https://pypi.tuna.tsinghua.edu.cn/simple'
  fi
  if [ -d ".venv" ]; then
    echo Virtual Environment already exists
    source .venv/bin/activate
    pip install -r requirements.txt $pyproxy
  else
    apt install python3-pip python3.12-venv -y
    echo Install Virtual Environment...
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt $pyproxy
  fi
elif [ "$1" == "clear" ]; then
    rm -fr "backend/__pycache__"
    rm -fr "backend/api/__pycache__"
    rm -fr "backend/utils/__pycache__"
elif [ "$1" == "app" ]; then # online_check
  if [ "$2" == "log" ]; then
    tail -f log-app.log
  elif [ "$2" == "kill" ]; then
    check_process_id $PROCESS_APP
    if [ $pid -gt 1 ]; then
      # tips
      echo -e "\033[34m kill -9 $pid \033[0m"
      kill -9 $pid
    else
      # tips
      echo -e "\033[31m Process: $PROCESS_MAIN is not exist. \033[0m"
    fi
    echo ""
  elif [ "$2" == "run" ]; then ## run
    check_process_id $PROCESS_APP
    if [ $pid -eq 0 ]; then
      echo Virtual Environment Activation...
      source .venv/bin/activate
      echo Launching $PROCESS_APP ...
      python3 $PROCESS_APP ${@:3}
    else
      # tips
      echo -e "\033[31m Process: $PROCESS_MAIN is exist. \033[0m"
    fi
  else
    check_process_id $PROCESS_APP
    if [ $pid -eq 0 ]; then
      echo Virtual Environment Activation...
      source .venv/bin/activate
      echo Launching $PROCESS_APP ...
      nohup python3 $PROCESS_APP ${@:2} > log-app.log 2>&1 &
    else
      # tips
      echo -e "\033[31m Process: $PROCESS_MAIN is exist. \033[0m"
    fi
  fi
elif [ "$1" == "log" ]; then
    tail -f log-main.log
elif [ "$1" == "kill" ]; then ## stop
  check_port $UVICORN_PORT
  if [ $pid -gt 1 ]; then
    # echo $pid
    if [ $pid -gt 1 ]; then
      # tips
      echo -e "\033[34m kill -9 $pid \033[0m"
      kill -9 $pid
    fi
    
    if [ "$(uname)" == "Darwin" ]; then
      temp=`netstat -anp tcp -v | grep ".$UVICORN_PORT " | awk '{print $11}' |sort |uniq |tr '\n' ' '`
      temp=${temp#*:}
      # tips
      echo -e "\033[34m kill $temp \033[0m"
      kill $temp
    else
      temp=`netstat -tlpn | grep ":$UVICORN_PORT " |grep -v "grep" |awk '{print $7}' |awk -F '/' '{print $1}' |sort |uniq |tr '\n' ' '`
      # tips
      echo -e "\033[34m kill -9 $temp \033[0m"
      kill -9 $temp
    fi
  else
    # tips
    echo -e "\033[31m Port: $UVICORN_PORT is not exist. \033[0m"
  fi
  echo ""
  
  check_process_id $PROCESS_MAIN
  if [ $pid -gt 1 ]; then
    # tips
    echo -e "\033[34m kill -9 $pid \033[0m"
    kill -9 $pid
  else
    # tips
    echo -e "\033[31m Process: $PROCESS_MAIN is not exist. \033[0m"
  fi
  echo ""
elif [ "$1" == "run" ]; then ## run
  check_port $UVICORN_PORT
  if [ $pid -eq 0 ]; then
    echo Virtual Environment Activation...
    source .venv/bin/activate
    echo Launching $PROCESS_MAIN ...
    python3 $PROCESS_MAIN ${@:2}
  else
    # tips
    echo -e "\033[31m Port: $UVICORN_PORT is exist. \033[0m"
  fi
else
  check_port $UVICORN_PORT
  if [ $pid -eq 0 ]; then
    echo Virtual Environment Activation...
    source .venv/bin/activate
    echo Launching $PROCESS_MAIN ...
    nohup python3 $PROCESS_MAIN $@ > log-main.log 2>&1 &
  else
    # tips
    echo -e "\033[31m Port: $UVICORN_PORT is exist. \033[0m"
  fi
fi
