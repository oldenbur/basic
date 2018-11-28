#!/bin/bash

# This script uses rsync to create a backup of the home directory
# contents.  The backup destination is the network drive tsl-01,
# which is mounted locally as /tsl-01.  The following /etc/fstab
# entry attempts to create this mount whenever the machine is 
# restarted:
#
# tsl-01:/devbu/poldenburg  /tsl-01  nfs  defaults  0  0
#
# The following crontab entry attempts to run the backup every
# evening at 2am and write the results to a log file in
# /var/log/backup.  The log files should eventually be aged off
# to save space on /var.
#
# 0 2 * * * /home/paul/src/backup/backup.sh
#

SRC_DIR=/home/paul
DEST_DIR=/tsl-01/backup/home
LOG_DIR=/var/log/backup
LOG_FILE=$LOG_DIR/backup_$(date +%Y%m%d_%H%M%S).log
REPORT=0

rsync -avz $SRC_DIR $DEST_DIR > $LOG_FILE 2>&1

RSYNC_EXIT=$?

if [[ $REPORT -ne 0 ]]; then
  echo "backup complete"
  echo "  exit code: $RSYNC_EXIT"
  echo "  log file: $LOG_FILE"
  echo "  log size: $(ls -lh $LOG_FILE | awk '{print $5}')"
fi

# on the first of the month, delete the logs from two months ago
DEL_SEC=$((3600 * 24 * 45))
if [ $(date +%d) -eq 1 ]; then

	DEL_EPOCH=$(( $(date +%s) - $DEL_SEC ))
	YM_DEL=$(date +%Y%m -d"1970-01-01 $DEL_EPOCH sec")
	DEL_PAT="$LOG_DIR/backup_$YM_DEL*.log"

	echo "deleting old logs: $DEL_PAT"
	rm -rf $DEL_PAT
fi

