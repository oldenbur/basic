import dropbox
import argparse
import os
import os.path
import time
import datetime
import contextlib
import sys

parser = argparse.ArgumentParser(description='Sync folders to Dropbox')
parser.add_argument('dbxdir', default='/Photos/2020.album', nargs='?', 
                    help='DropBox directory')
parser.add_argument('localdir', default='c:\\Users\\ahild\\Pictures\\paul\\2020.album', nargs='?',  
                    help='File system directory')
parser.add_argument('-d', '--dryrun', action="store_true",
                    help='Don\'t upload anything')

def main():
    args = parser.parse_args()

    print "img_copy starting\n  dbxdir: %s\n  localdir: %s" % (args.dbxdir, args.localdir)

    token = os.environ['DROPBOX_OAUTH_SECRET']
    if not token:
        print 'ERROR: please set DROPBOX_OAUTH_SECRET with an auth token \
                (see https://www.dropbox.com/developers/apps)'
        return

    if args.dryrun:
        file_uploader = lambda fs_filepath, dbx_path: \
            file_uploader_print(fs_filepath, dbx_path)
        dir_creator = lambda dir: dir_creator_print(dir)
    else:
        file_uploader = lambda fs_filepath, dbx_path: \
            dbx_upload(dbx, 
                fs_filepath, 
                dbx_path + "/" + os.path.basename(fs_filepath)
            )
        dir_creator = lambda dir: dbx_mkdir(dbx, dir)

    dbx = dropbox.Dropbox(token)
    fs_recurse_dir(dbx, args.localdir, args.dbxdir,
        lambda fs_filepath, dbx_path: file_uploader(fs_filepath, dbx_path),
        lambda dir: dir_creator(dir),
    )

def dir_creator_print(dir):
    print "dry run not mkdir\n  dbx_path: %s" % dir
    return None

def file_uploader_print(fs_filepath, dbx_path):
    print "dry run not uploading\n  fs_filepath: %s\n  dbx_path: %s" % (fs_filepath, dbx_path)
    return None

def fs_recurse_dir(dbx, fs_path, dbx_path, file_uploader, dir_creator):

    for dirpath, dirnames, filenames in os.walk(fs_path):
        
        print "\nfs_recurse_dir:\n  fs_path: %s\n  dirpath: %s" % (fs_path, dirpath)

        dbx_pathdir = dbx_path + dirpath.replace(fs_path, "").replace("\\", "/")
        if not dbx_dir_exists(dbx, dbx_pathdir):
            dir_creator(dbx_pathdir)

        dbx_files = dbx_dir_files(dbx, dbx_pathdir)
        for fs_file in filenames:   
            if fs_file not in dbx_files:
                fs_filepath = os.path.join(dirpath, fs_file)
                # print "\n" + fs_filepath + " - MISSING - uploading to " + dbx_pathdir
                sys.stdout.flush()
                file_uploader(fs_filepath, dbx_pathdir)
            

def dbx_dir_files(dbx, dbx_path):
    """Returns a list of dropbox filenames as strings in the specified path.
    """
    files = {}
    try:
        dbx_files = dbx.files_list_folder(dbx_path)
    except dropbox.exceptions.ApiError as e:
        print "WARNING: dropbox folder access '{0}' failed: {1}".format(dir, e)
        return files

    for m in dbx_files.entries:
        if type(m) == dropbox.files.FileMetadata:
            files[m.name] = m

    return files


def dbx_upload(dbx, fs_filepath, dbx_filepath, overwrite=False):
    """Upload the file system file to the specified location in dropbox.
    Return the request response, or None in case of error.
    """
    print '\ndbx_upload\n   fs_filepath: %s\n  dbx_filepath: %s' % (fs_filepath, dbx_filepath)

    mode = (dropbox.files.WriteMode.overwrite
            if overwrite
            else dropbox.files.WriteMode.add)
    mtime = os.path.getmtime(fs_filepath)
    with open(fs_filepath, 'rb') as f:
        fs_data = f.read()
    with stopwatch('dbx_upload complete\n  fs_filepath: %s (%d bytes)' % (fs_filepath, len(fs_data))):
        try:
            res = dbx.files_upload(
                fs_data, dbx_filepath, mode,
                client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
                mute=True)
        except dropbox.exceptions.ApiError as e:
            print "WARNING: dropbox upload failed: {0}".format(e)
            return None

    print 'dbx_upload as ' + res.name.encode('utf8')
    return res


def dbx_mkdir(dbx, dbx_path):

    with stopwatch('dbx_mkdir complete\n  dbx_path: %s' % (dbx_path)):
        try:
            return dbx.files_create_folder_v2(dbx_path)
        except dropbox.exceptions.ApiError as e:
            print "WARNING: dropbox create_folder failed: {0}".format(e)
            return None


def dbx_dir_exists(dbx, dbx_path):

    with stopwatch('dbx_dir_exists complete\n  dbx_path: %s' % (dbx_path)):
        try:
            meta = dbx.files_get_metadata(dbx_path)
            # print 'dbx_dir_exists meta: {0}'.format(meta)
            return True
        except dropbox.exceptions.ApiError as e:
            if not e.error.is_path() or not e.error.get_path().is_not_found():
                print "WARNING: dropbox files_get_metadata failed: {0}".format(e)
            return False


@contextlib.contextmanager
def stopwatch(message):
    """Context manager to print how long a block of code took."""
    t0 = time.time()
    try:
        yield
    finally:
        t1 = time.time()
        print('Total elapsed time for %s: %.3f' % (message, t1 - t0))


if __name__ == '__main__':
    main()