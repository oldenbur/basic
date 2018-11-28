#!/bin/bash 

# taken from http://git.661346.n2.nabble.com/Git-ksshaskpass-to-play-nice-with-https-and-kwallet-td6858195.html
#
# put this script on the path and run:
# $ git config --global core.askpass ~/bin/git-ksshaskpass 

set $* 
exec ksshaskpass $1\@$3 

