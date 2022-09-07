#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: paktool $
#
# IBM CONFIDENTIAL
#
# EKB Project
#
# COPYRIGHT 2022
# [+] International Business Machines Corp.
#
#
# The source code for this program is not published or otherwise
# divested of its trade secrets, irrespective of what has been
# deposited with the U.S. Copyright Office.
#
# IBM_PROLOG_END_TAG


############################################################
# Imports - Imports - Imports - Imports - Imports - Imports
############################################################
# Python provided
import argparse
import time
import datetime
import sys
import os
import textwrap
# For doing a tree listing of archive contents
from collections import defaultdict
def tree(): return defaultdict(tree)

# Add program modules to the path
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pymod"))
from output import out
import pakcore as pak
import pakutils

############################################################
# Functions - Functions - Functions - Functions - Functions
############################################################
# The cmd_* functions correspond to the top level command line option
def cmd_add(args):
    '''
    Add files to the archive from the command line
    If output archive specified exists, it will try to load that data in first
    '''
    # Create and load the archive
    archive = pak.Archive(args.archive)
    if os.path.isfile(args.archive):
        archive.load()

    # Go through all files passed in and process
    addFiles = list()
    for fname in args.file:
        # A directory, try to load in everything under that
        if os.path.isdir(fname):
            for dirpath, _, dirfiles in os.walk(fname):
                for name in dirfiles:
                    addFiles.append(os.path.join(dirpath, name))
        elif os.path.isfile(fname):
            addFiles.append(fname)
        else:
            raise pak.ArchiveError("File not found: " + fname)

    # All the input files have been processed, put them into the archive
    for fname in addFiles:
        with open(fname, "rb") as f:
            archive.add(fname, args.method, f.read())

    # Write the new or updated archive
    return archive.save()

def cmd_extract(args):
    '''
    Extract files out of the given archive to the path specified
    '''
    # Create and load the archive
    archive = pak.Archive(args.archive)
    archive.load()

    # Filter the list
    result = archive.find(args.file)

    # Write the files
    for entry in result:
        ename = os.path.join(args.outdir, entry.name)
        out.print("Extracting %s -> %s " % (entry.name, ename))
        os.makedirs(os.path.dirname(ename), exist_ok=True)
        with open(ename, "wb") as f:
            f.write(entry.ddata)

def cmd_list(args):
    '''
    List the contents of an archive and the pak header information
    '''
    # Create and load the archive
    result = pak.Archive(args.archive)
    result.load()

    # If selected, find any embedded paks and expand them
    # The search for paks is based on the file name ending in .pak
    # This could be expanded to byte-peep each file and look for pak headers,
    # but that is a more complicated implementation.  Let's hope .pak sanity prevails
    if (args.expand):
        # We can have paks in paks in paks, so this needs to be a recursive find until we run out
        while True:
            try:
                paksInPaks = result.find("*.pak")
            except:
                # An exception is raised when no match is found
                # That means we are out of paks and done
                break

            # The search worked and we have the list of the paks embedded within this archive
            for embedFile in paksInPaks:
                # For each one, create a new archive and load it
                # This will let us get to the contents of the pak for expansion
                embedArchive = pak.Archive()
                # Send in the decompressed data, which is the full contents of the embedded pak
                embedArchive.load(image=embedFile.ddata)
                for file in embedArchive:
                    # For each file in the archive, update the name relative to the original pak
                    file.name = embedFile.name + ">/" + file.name
                    # Insert that file into the original pak at the location found in original pak
                    result.insert(result.index(embedFile), file)
                # Remove the original embedded pak, all its contents is now in the original pak for display
                result.remove(embedFile)

    # Filter the list
    # Do the input find filters after the optional expansion
    result = result.find(args.file)

    # Rebuild the image after the filtering and expanding
    result.build()

    if (args.details):
        # Utilize the entry debug code to provide the detailed info on each entry
        for entry in result:
            entry.display()
    else:
        # Print an easy to read tree of the archive contents
        # An elm is a good tree
        elm = tree()

        # Loop through the flat list of files to build a tree representation of the layout
        for entry in result:
            # Start at the top of the tree for each branch we build
            branch = elm
            # Split the file name into its 'directory' pieces
            # The loop through each piece and build the tree
            nameparts = entry.name.split('/')
            for part in nameparts:
                if (nameparts[-1] == part):
                    # The last entry in parts is the file
                    # Stick the entry into the branch in case we need any part of it during print
                    branch[entry] = True
                else:
                    # Any other part is a branch in tree
                    # If it doesn't already exist, create it
                    if (part not in branch):
                        branch[part] = tree()
                    # Advance our branch as we descend down
                    branch = branch[part]

        # Display what we've built
        print_tree(elm, root=os.path.basename(args.archive))

    # Common output of file info
    # Get counts of files vs pads and put them into the summary
    fileCount = len([x for x in result if (x.magic == pak.PAK_FILE)])
    padCount = len([x for x in result if (x.magic == pak.PAK_PAD)])
    summary = "\n%d files" % fileCount
    if (padCount):
        summary += ", %d pads" % padCount
    # Add file size info and then display
    summary += ", total size: %s (0x%08X)" % (pakutils.humanBytes(len(result.image)), len(result.image))
    out.print(summary)

def cmd_remove(args):
    '''
    Remove file(s) from an archive and then rewrite it to same location
    '''
    # Create and load the archive
    archive = pak.Archive(args.archive)
    archive.load()

    # Filter the list
    result = archive.find(args.file)

    # Now go through the resolved entries and remove
    # The remove is done against the original archive
    for entry in result:
        out.print("Removing %s" % entry.name)
        archive.remove(entry)

    # Write it back out
    return archive.save()

def cmd_hash(args):
    '''
    Hash the contents of an archive and write it to a file
    '''
    # Create and load the archive
    archive = pak.Archive(args.archive)
    archive.load()

    # Filter the list
    result = archive.find(args.file)

    # Create all the hashes for the selected files
    out.print("Creating hashes")
    out.moreIndent()
    for entry in result:
        out.print(entry.name)
        entry.hash(i_algorithm=args.algorithm)
    out.lessIndent()

    # Now write out the file
    with open(args.hashfile, "wb") as f:
        out.print("Writing hash", args.hashfile)
        contents = result.createHashList(i_algorithm=args.algorithm)
        f.write(contents)

    return

def cmd_merge(args):
    '''
    Merge archives. If there are duplicate entrees in the archive, the last one is used
    '''
    # if target exist then load it.
    target = pak.Archive(args.archive)
    if os.path.isfile(args.archive):
        target.load()

    for afile in args.file:
        if os.path.isfile(afile):
            arc = pak.Archive(afile)
            arc.load()
            for file in arc:
                target.append(file)
        else:
            raise pak.ArchiveError("File not found: " + afile)

    return target.save()

# Support functions for cmd_* functions
def print_tree(branch, root=None, prefix=''):
    '''
    Walk the tree passed in and print info about it
    This mimics the output of the tree cmdline
    '''
    # The tree is anchored to the root, will be set by the top level caller
    # All recursive calls within this function will not set root
    if (root):
        out.print(root)

    # Loop through the tree by its keys
    # This makes it easier to identify the last key at each layer
    # That's important for properly formatting the output
    keys = list(branch.keys())
    for key in keys:
        # Start to build our output line
        # The prefix has all the stuff to the left of the current entry we are building on
        line = prefix
        # Identify the last entry in the list to setup both our current line and what we add to prefix
        last = (keys[-1] == key)
        if (last):
            line += '`-- '
            addfix = '    '
        else:
            line += '|-- '
            addfix = '|   '
        # We can have two different types of keys, str or ArchiveEntry
        if type(key) == str:
            line += key
        else:
            # Just grab the last part of the archive entry to display the name
            if (key.magic == pak.PAK_FILE):
                line += os.path.basename(key.name)
            else:
                line += "|<pad>|"
            # Optionally add more info about the file to the output
            # Disabled for now, anything done here needs to be very clean to keep the output readable
            if (False):
                line += " [%s]" % (pakutils.humanBytes(key.csize))
        # We have built the full line, display it
        out.print(line)

        # Lastly, keep going if there is another layer
        if type(branch[key]) == defaultdict:
            print_tree(branch[key], prefix=prefix + addfix)

    return

############################################################
# Main - Main - Main - Main - Main - Main - Main - Main
############################################################
rc = 0
progStartTime = time.time()
# Create a generic time stamp we can use throughout the program
timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

################################################
# Command line options
# Create the argparser object
parser = argparse.ArgumentParser(description="Work with hardware .pak files")

# Add optional args shared across all commands
parser.add_argument('-c', '--console-level', default=out.levels.WARN, type=out.levels.argparse, choices=list(out.levels),
                      help="The output level to send to send to the console.  WARN is the default")

# Create the sub parser that we'll add each of our sub commands
subparsers = parser.add_subparsers()

# add sub command
sub = subparsers.add_parser("add", description="Add files to an archive or replace existing files",
                            formatter_class=argparse.RawDescriptionHelpFormatter)
sub.add_argument("archive", help="Archive file, will be created if it does not exist")
sub.add_argument("file", nargs="+", help="List of files to add; directories will be added recursively")
sub.add_argument("-m", "--method", default=pak.CM.zlib, type=pak.CM.argparse, choices=list(pak.CM), help="Compression method to use")
sub.epilog = textwrap.dedent('''

examples:
  > paktool add archive file1 file2
''')
sub.set_defaults(func=cmd_add)

# hash sub command
sub = subparsers.add_parser("hash", description="Hash a set of archived files")
sub.add_argument("archive", help="Archive file")
sub.add_argument("hashfile", help="File name to write the resulting hash data to")
sub.add_argument("file", nargs="*", help="List of files to hash; their compressed data will be hashed one after the other. If no files are provided, all files in the archive will be hashed.")
sub.add_argument("-a", "--algorithm", default="sha3_512", help="Hashing algorithm to use; default is sha3_512")
sub.set_defaults(func=cmd_hash)

# extract sub command
sub = subparsers.add_parser("extract", description="Extract files from an archive")
sub.add_argument("archive", help="Archive file")
sub.add_argument("file", nargs="*", help="List of files to extract; if none are given, all files will be extracted")
sub.add_argument("-o", "--outdir", default=".", help="Output directory, defaults to current directory")
sub.set_defaults(func=cmd_extract)

# list sub command
sub = subparsers.add_parser("list", description="List files in an archive",
                            formatter_class=argparse.RawDescriptionHelpFormatter)
sub.add_argument("archive", help="Archive file")
sub.add_argument("file", nargs="*", help="List of files to list; if none are given, all files will be listed")
sub.add_argument("-d", "--details", action='store_true', help="Print details")
sub.add_argument("-e", "--expand", action="store_true", help="Expand out any embedded paks")
sub.epilog = textwrap.dedent('''

examples:
  > paktool list archive
  > paktool list archive file1 file2
  > paktool list archive -d
''')
sub.set_defaults(func=cmd_list)

# remove sub command
sub = subparsers.add_parser("remove", description="Remove files from an archive")
sub.add_argument("archive", help="Archive file")
sub.add_argument("file", nargs="*", help="List of files to remove; if none are given, all files will be removed")
sub.set_defaults(func=cmd_remove)

# merge sub command
sub = subparsers.add_parser("merge", description='''
        Merge archives. If target archive exists, it's loaded first.
        If duplicate entree names exist between archives then only the last will be included.''')
sub.add_argument("archive", help="Target archive file")
sub.add_argument("file", nargs="*",help="List of archive files to merge into archive")
sub.epilog = textwrap.dedent('''
examples:
    > paktool merge target_archive  archive1 archive2
''')
sub.set_defaults(func=cmd_merge)


# cmdline loaded up, now parse for it and handle what is found
args = parser.parse_args()
if not hasattr(args, "func"):
    parser.print_help()
    sys.exit(1)

# Set the console output level selected
out.setConsoleLevel(args.console_level)

# Call the function defined for each sub command
try:
    args.func(args)
except pak.ArchiveError as e:
    out.error(str(e))
    sys.exit(1)
