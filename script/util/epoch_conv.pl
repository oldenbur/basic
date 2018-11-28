#!/usr/bin/perl

use POSIX;
use Date::Parse;

@ARGV or print "usage: $0 {epoch|time}
  where:
    epoch is the epoch to convert, with or without commas, in sec or millis
    time is a time string of reasonable format
" and exit;

$_ = $ARGV[0];
$s = join(' ', @ARGV);
if( /^\d[,\d]+\d$/ ){  # epoch
	s/,//g;
	$e = $_;
	$e = $e > 1e10 ? $e/1000 : $e;
} elsif( !defined($e = str2time($s)) ) {
	die "ERROR: unable to parse input: $_\n";
}

print " epoch: $e\n";
print " local: " . strftime("%Y/%m/%d %H:%M:%S %Z", localtime($e)) . "\n";
print "gmtime: " . strftime("%Y/%m/%d %H:%M:%S UTC", gmtime($e)) . "\n";

