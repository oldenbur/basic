import dropbox
import argparse
import os

parser = argparse.ArgumentParser(description='Sync folders to Dropbox')
parser.add_argument('dbxdir', default='/Photos', help='DropBox directory')

def main():
    args = parser.parse_args()

    print "img_copy starting\n  dbxdir: %s\n" % (args.dbxdir)

    token = os.environ['DROPBOX_OAUTH_SECRET']
    if not token:
        print 'ERROR: please set DROPBOX_OAUTH_SECRET with an auth token \
                (see https://www.dropbox.com/developers/apps)'
        return

    dbx = dropbox.Dropbox(token)
    dbx_recurse_dir(dbx, args.dbxdir)


def print_name(m): print m.name


def dbx_recurse_dir(dbx, dir_name, file_visitor=print_name):
   
    print "dbx_recurse_dir(%s)" % dir_name
    dbx_files = dbx.files_list_folder(dir_name)

    files = []
    folders = []
    for m in dbx_files.entries:
        if type(m) == dropbox.files.FileMetadata:
            files.append(m)
        elif type(m) == dropbox.files.FolderMetadata:
            folders.append(m)

    folders = sorted(folders, key=lambda m: m.name)
    for f in folders:
        dbx_recurse_dir(dbx, dir_name + "/" + f.name, file_visitor)

    files = sorted(files, key=lambda m: m.name)
    for f in files: file_visitor(f)


if __name__ == '__main__':
    main()