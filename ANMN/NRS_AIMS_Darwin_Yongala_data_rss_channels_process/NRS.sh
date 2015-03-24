#!/bin/bash

function read_env(){
    export LOGNAME=projectofficer
    export HOME=/home/projectofficer
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games

    script_bash_path=`readlink -f $0`
    script_dir=`dirname $script_bash_path`
    env_path=$script_dir"/env"
    if [ ! -f `readlink -f $env_path` ]
    then
        echo "env file does not exist. exit" 2>&1
        exit 1
    fi

    # read environmental variables from config.txt
    source `readlink -f $env_path`

    # subsistute env var from config.txt | delete lines starting with # | delete empty lines | remove empty spaces | add export at start of each line
    source /dev/stdin <<<  `envsubst  < $script_dir/config.txt | sed '/^#/ d' | sed '/^$/d' | sed 's:\s::g' | sed 's:^:export :g' `
}


function main(){
    read_env

    APP_NAME=ANMN_NRS_DAR_YON_DOWNLOAD
    DIR=/tmp
    lockfile=${DIR}/${APP_NAME}.lock

    {
        if ! flock -n 9
        then
          echo "Program already running. Unable to lock $lockfile, exiting" 2>&1
          exit 1
        fi

        echo START ${APP_NAME}
        run_matlab
        run_rsync

        rm $lockfile

    } 9>"$lockfile"
}


function run_matlab(){
    matlab_script_name=NRS_Launcher.m
    matlab -nodisplay -r "run  ('"${script_dir}"/"${matlab_script_name}"');exit;"  2>&1 | tee  ${DIR}/${APP_NAME}.log ;
}


function run_rsync(){
    rsync --size-only --itemize-changes --delete-before  --stats -uhvrD  --progress ${data_opendap_rsync_path}/opendap/${siteDAR}/ ${destination_production_data_path}/${siteDAR}/ ;
    rsync --size-only --itemize-changes --delete-before  --stats -uhvrD  --progress ${data_opendap_rsync_path}/opendap/${siteYON}/ ${destination_production_data_path}/${siteYON}/ ;
}

main

