from datetime import *
import argparse

tsformat = '%Y%m%d'
tsformatw = '%Y%m%d_%H%M%S'
tsnow = datetime.now()
today = tsnow.strftime(tsformat)
#print 'today: {}'.format(today)

parser = argparse.ArgumentParser(description='Calculate date differences in days')
parser.add_argument('-s', default=today, nargs='?', required=False,
                    help='optional start date as YYYYmmdd (default today)')
parser.add_argument('-e', nargs='?', required=True, help='end date as YYYYmmdd')
parser.add_argument('-d', nargs='?', help='delta in days to subtract from e')
args = parser.parse_args()

tsend = datetime.strptime(args.e, tsformat)
if args.d:
    tsstart = tsend - timedelta(int(args.d))
else:
    tsstart = datetime.strptime(args.s, tsformat)
deltadays = tsend - tsstart

print 'start: {}  end: {}  delta: {}'. \
        format(tsstart.strftime(tsformatw), tsend.strftime(tsformatw), deltadays)


