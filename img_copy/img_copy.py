import dropbox
import argparse
import os

parser = argparse.ArgumentParser(description='Sync folders to Dropbox')
parser.add_argument('dbxdir', default='/Photos/2000.album', nargs='?', help='DropBox directory')
parser.add_argument('localdir', default='c:\\Users\\ahild\\Pictures\\paul\\2000.album', nargs='?',  
                    help='File system directory')

def main():
    args = parser.parse_args()

    print "img_copy starting\n  dbxdir: %s\n  localdir: %s\n\n" % (args.dbxdir, args.localdir)

    token = os.environ['DROPBOX_OAUTH_SECRET']
    if not token:
        print 'ERROR: please set DROPBOX_OAUTH_SECRET with an auth token \
                (see https://www.dropbox.com/developers/apps)'
        return

    dbx = dropbox.Dropbox(token)
    #dbx_recurse_dir(dbx, args.dbxdir)
    fs_recurse_dir(args.localdir, dbx_dir_file_getter(dbx, args.dbxdir))


def printer(s): print s
def noop(s): pass

def dbx_dir_file_getter(dbx, dbx_dir):
    return lambda dir: dbx_dir_files(dbx, dbx_dir + "/" + dir)


def fs_recurse_dir(dir, comp_files):

    for dirpath, dirnames, filenames in os.walk(dir):
        dbx_files = comp_files(dirpath.replace(dir, "").replace("\\", "/"))
        for fs_file in filenames:
            if fs_file in dbx_files:
                print fs_file + " - FOUND"
            else:
                print fs_file + " - MISSING"


def print_meta_name(m): print m.name

def dbx_dir_files(dbx, dir):
   
    files = {}
    try:
        dbx_files = dbx.files_list_folder(dir)
    except dropbox.exceptions.ApiError as e:
        print "WARNING: dropbox folder access '{0}' failed: {1}".format(dir, e.user_message_text)
        return files

    for m in dbx_files.entries:
        if type(m) == dropbox.files.FileMetadata:
            files[m.name] = m

    return files


if __name__ == '__main__':
    main()