#!/usr/bin/python3


"""
Downloads files.
"""


import os
import sqlite3
from utils.consoleaccessories import is_valid_path
from utils.consoleaccessories import clean_path
from utils.debugtools import count_downloadable_images
from utils.politeness import get_politeness_factor


DB_TEMPLATE = """
DROP TABLE IF EXISTS images;

CREATE TABLE images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  PostUrl TEXT,
  ImageUrl TEXT,
  Filename TEXT,
  Domain TEXT,
  PostTitle TEXT,
  CommentSectionUrl TEXT,
  PostedOn TEXT,
  LastHtmlStatusCode INTEGER,
  Downloaded INTEGER,
  DownloadDate TEXT
);
"""

def download_files(files, destination, verbose):
    """
    This function downloads files to a specified directory. Destination
    is a path to a directory where images will be stored. If verbose is
    True, then the download status is displayed.
    """
    current_directory = os.getcwd()
    os.chdir(destination)

    # Since directory has changed, you do not have to use abs path for db
    # you could use './db.sqlite'
    # in that case, there is no need to clean path
    db_path = ''.join([clean_path(path), '/db.sqlite'])

    # Check if db exists in destination directory
    if not is_valid_path(db_path):
        conn = make_connection(db_path)
        c = conn.cursor()
        c.executescript(DB_TEMPLATE)
        conn.commit()

    conn = make_connection(db_path)
    c = conn.cursor()

    # Download, deal with exception, save to db, log things...
    total = count_downloadable_images(files)
    currently_downloading = 1
    while files:
        file_obj = files.popleft()

        if file_obj['image']['image_url']:
            if verbose: display_status(file_obj['image']['image_url'], currently_downloading, total)

    conn.close()
    os.chdir(current_directory)


def make_connection(path):
    """
    Make connection to database.
    """
    return sqlite3.connect(path)
