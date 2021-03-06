#!/usr/bin/python

import argparse
import re
import subprocess
import sys

import discuss
import discuss.rpc
import discuss.constants

ACL_ALL = 'acdorsw'
ACL_READ = 'rs'
ACL_WRITE = 'aorsw'

def validate_name(name):
    validator = '^[a-zA-Z0-9._-]+$'
    basic_chars = bool(re.match(validator, name))
    parent = bool(re.search('[.][.]', name))
    return basic_chars and not parent

def meeting_path(name):
    return "/var/spool/discuss/%s" % (name, )

def fill_defaults(args):
    if not args.longname:
        args.longname = args.name
    args.name = args.name.lower()
    if not args.path:
        args.path = meeting_path(args.name)

def parse_args(full=True):
    """Parse arguments to this script.

    full: allow potentially-dangerous options? When false, the only options
    defined are those that should be reasonably safe to expose to
    mostly-untrusted users using remctl, a web form, or similar interfaces.
    """
    parser = argparse.ArgumentParser(description="Create discuss meeting")
    parser.add_argument('--public', type=bool, help='should the meeting be public?', default=True)
    if full:
        parser.add_argument('--server', help='remote discuss server to use [If unset, the local backend will be used. Setting this option also disables setting up the mail feed.]')
        parser.add_argument('--path', help='path to the meeting to be created (default is based on the short name)')
    parser.add_argument('--longname', help='long name of meeting (defaults to the short name)')
    parser.add_argument('name', help='short name of meeting')

    # Other fields accepted by mkds:
    # - additional users to put on the ACL (with aorsw)
    # - initial transaction
    # - announce meeting

    args = parser.parse_args()
    if not full:
        # Fill out the default argument values
        args.server = None
        args.path = None
    # We validate the name but not the path -- we expect --path to be used only
    # rarely, and then by fully-trusted users. When --path is set
    # automatically, validating name also validates the derived path.
    if not validate_name(args.name):
        parser.error("Illegal meeting name")
    fill_defaults(args)
    return args

class MakeMeetingArgs(object):
    def __init__(self, shortname, public, longname=None, validate=True, ):
        self.public = public
        self.server = None
        self.path = None
        self.longname = longname
        self.name = shortname
        if validate:
            if not validate_name(shortname):
                raise ValueError("Illegal meeting name")
        fill_defaults(self)

def make_mailfeed(args):
    # WARNING: assumes that path is safe
    line_tmpl = '%(name)s-mtg: "|/usr/local/bin/dsmail -d -s 20 %(path)s"\n'
    line = line_tmpl % vars(args)
    with open('/var/spool/discuss/control/aliases', 'a') as aliases:
        aliases.write(line)
    subprocess.check_call(['/usr/sbin/postalias', 'aliases'], cwd='/var/spool/discuss/control/')

def make_meeting(args):
    if args.server:
        rpc = discuss.rpc.RPCClient
    else:
        rpc = discuss.rpc.RPCLocalClient
    cl = discuss.Client(args.server, RPCClient=rpc)
    error = cl.create_mtg(args.path, args.longname, args.public)
    make_mailfeed(args)
    return discuss.Meeting(cl, args.path)

def get_local_meeting(shortname):
    rpc = discuss.rpc.RPCLocalClient
    cl = discuss.Client('localhost', RPCClient=rpc)
    return discuss.Meeting(cl, meeting_path(shortname))

whitelist_access = [
    'daemon.diswww@ATHENA.MIT.EDU', # web access
    'daemon@ATHENA.MIT.EDU',        # mail feed
    'discuss@ATHENA.MIT.EDU',       # admin / alternative mail feed
    'pergamon-dsadmin@ATHENA.MIT.EDU',  # admin (remctls, for example
]

def set_default_perms(meeting):
    meeting.ensure_access('daemon.diswww@ATHENA.MIT.EDU', ACL_READ)
    meeting.ensure_access('daemon@ATHENA.MIT.EDU', ACL_WRITE)
    meeting.ensure_access('discuss@ATHENA.MIT.EDU', ACL_WRITE)
    meeting.ensure_access('pergamon-dsadmin@ATHENA.MIT.EDU', ACL_ALL)

if __name__ == '__main__':
    full = sys.argv[0].endswith('/make_meeting')
    args = parse_args(full)
    make_meeting(args)
