#!/usr/bin/perl

use strict;
use warnings;

my $note_file = $ENV{NOTES_HOME} . "/notes.txt";
open(my $fh, "<", $note_file) or die "cannot open $note_file: $!\n";

# read and filter the lines in the notes file
my @filt_lines = <$fh>;
for my $key (@ARGV){
	my $key_uc = uc($key);
	@filt_lines = grep(/$key_uc/, @filt_lines);
}
chomp(@filt_lines);

# determine the max width of the headers for the filtered lines
my $pfx_wid = 0;
for (@filt_lines){
	/^([^\|]+) \| /;
	$pfx_wid = length($1) > $pfx_wid ? length($1) : $pfx_wid;
}

# print the filtered lines with formatted header width
for (@filt_lines){
	/^([^|]+) \| (.+)/ or next;
	printf "%-*s | %s\n", $pfx_wid, $1, $2;
}


