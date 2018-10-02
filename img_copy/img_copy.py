import dropbox
import argparse
import os

parser = argparse.ArgumentParser(description='Sync folders to Dropbox')
parser.add_argument('dbxdir', default='/Photos', help='DropBox directory')

def main():
    print "img_copy starting"

    args = parser.parse_args()

    token = os.environ['DROPBOX_OAUTH_SECRET']
    if not token:
        print 'ERROR: please set DROPBOX_OAUTH_SECRET with an auth token \
                (see https://www.dropbox.com/developers/apps)'
        return

    dbx = dropbox.Dropbox(token)
    dbx_files = dbx.files_list_folder(args.dbxdir)
    print dbx_files


if __name__ == '__main__':
    main()