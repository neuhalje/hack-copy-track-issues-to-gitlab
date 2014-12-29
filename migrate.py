import re
from re import MULTILINE
import sys
import xmlrpclib
import gitlab
"""
What
=====

 This script migrates issues from trac to gitlab.
 * Component & Issue-Type are converted to labels
 * Milestones are ignored (or: I did not get the script to set my one single milestone, so I set it manually)
 * Comments to issues are copied over
 * Wiki Syntax in comments/descriptions is sanitized for my basic usage


How
====

 Usage: configure the following variables in in ```migrate.py````

Source
-------

 * ```trac_url``` - xmlrpc url to trac, e.g. ``https://user:secret@www.example.com/projects/taskninja/login/xmlrpc```

Target
-------

 * ```gitlab_url``` - e.g. ```https://www.exmple.com/gitlab/api/v3```
 * ```gitlab_access_token``` - the access token of the user creating all the issues. Found on the account page,  e.g. ```secretsecretsecret```
 * ```dest_project_name``` - the destination project including the paths to it. Basically the rest of the clone url minus the ".git". E.g. ```jens.neuhalfen/task-ninja```.
 * ```milestone_map``` - Maps milestones from trac to gitlab. Milestones have to exist in gitlab prior to running the script (_CAVE_: Assigning milestones does not work.)
 * ```milestone_list``` - Lists milestones from trac with associated metadata. Manually populated at this point by copy/paste out of trac milestone admin page

License
========

 License: http://www.wtfpl.net/

Requirements
==============

 * ```Python 2.7, xmlrpclib, requests```
 * Trac with xmlrpc plugin enabled
 * Gitlab

"""
trac_url = "https://user:secret@www.example.com/projects/taskninja/login/xmlrpc"

gitlab_url = "https://www.exmple.com/gitlab/api/v3"
gitlab_access_token = "secretsecretsecret"



dest_project_name ="jens.neuhalfen/task-ninja"
milestone_map = {
				  "Sprint 001":"Sprint 001","Sprint 002":"Sprint 002","Sprint 003":"Sprint 003","Sprint 004":"Sprint 004",
                  "Sprint 005":"Sprint 005","Sprint 006":"Sprint 006","Sprint 007":"Sprint 007","Sprint 008":"Sprint 008",
                  "Sprint 009":"Sprint 009","Sprint 010":"Sprint 010"
                }

milestone_list = {
                    "Sprint 001":{"title":"Sprint 001","description":"your description here","due_date":"2013-02-11"},
                    "Sprint 002":{"title":"Sprint 002","description":"etcetera","due_date":"2013-05-06"},
                    "Sprint 003":{"title":"Sprint 003","description":"","due_date":"2013-05-20"},
                    "Sprint 004":{"title":"Sprint 004","description":"","due_date":"2013-06-03"},
                    "Sprint 005":{"title":"Sprint 005","description":"","due_date":"2013-06-10"},
                    "Sprint 006":{"title":"Sprint 006","description":"","due_date":"2013-06-14"},
                    "Sprint 007":{"title":"Sprint 007","description":"","due_date":"2013-06-21"},
                    "Sprint 008":{"title":"Sprint 008","description":"","due_date":"2013-08-15"},
                    "Sprint 009":{"title":"Sprint 009","description":"","due_date":"2013-08-25"},
                    "Sprint 010":{"title":"Sprint 010","description":"","due_date":"2013-09-10"}
                 }
"------"



def fix_wiki_syntax(markup):
    markup = re.sub(r'#!CommitTicketReference.*\n',"",markup, flags=MULTILINE)

    markup = markup.replace("{{{\n","\n```text\n")
    markup = markup.replace("{{{","```")
    markup = markup.replace("}}}","```")

    # [changeset:"afsd38..2fs/taskninja"] or [changeset:"afsd38..2fs"]
    markup = re.sub(r'\[changeset:"([^"/]+?)(?:/[^"]+)?"]',r"changeset \1",markup)
    print >>sys.stderr, "\nProcessing comment markup..."
    return markup

def get_dest_project_id(dest_project_name):
    dest_project = dest.project_by_name(dest_project_name)
    if not dest_project: raise ValueError("Project '%s' not found under '%s'" % (dest_project_name, gitlab_url))
    return dest_project["id"]

def get_dest_milestone_id(dest_project_id,milestone_name):
    dest_milestone_id = dest.milestone_by_name(dest_project_id,milestone_name )
    
    if not dest_milestone_id:
        print >>sys.stderr, "\nGitLab milestone not found, creating one for\n %s" % (milestone_list[milestone_name])
        dest.create_milestone(dest_project_id,milestone_list[milestone_name])
        dest_milestone_id = dest.milestone_by_name(dest_project_id,milestone_name )
        # print >>sys.stderr, "\nGitLab milestone id: %s\n" % (dest_milestone_id["id"])

    return dest_milestone_id["id"]



#if __name__ == "__main__":
#   for v  in ['[changeset:"7609b4a46141a61d8f1e4a3e9c9d4f013e0388f8"]:','[changeset:"7609b4a46141a61d8f1e4a3e9c9d4f013e0388f8/taskninja"]:']:
#    print(v, fix_wiki_syntax(v))

if __name__ == "__main__":
    dest = gitlab.Connection(gitlab_url,gitlab_access_token)
    source = xmlrpclib.ServerProxy(trac_url)

    dest_project_id = get_dest_project_id(dest_project_name)
    milestone_map_id={}
    for mstracname, msgitlabname in milestone_map.iteritems():
        milestone_map_id[mstracname]=get_dest_milestone_id(dest_project_id, msgitlabname)



    get_all_tickets = xmlrpclib.MultiCall(source)

    for ticket in source.ticket.query("max=0&order=id&asc=1"):
        get_all_tickets.ticket.get(ticket)


    for src_ticket in get_all_tickets():
        src_ticket_id = src_ticket[0]
        src_ticket_data = src_ticket[3]

        is_closed =  src_ticket_data['status'] == "closed"
        new_ticket_data = {
            "title" : src_ticket_data['summary'],
            "description" : fix_wiki_syntax( src_ticket_data['description']),
            "closed" : 1 if is_closed else 0,
            "labels" : ",".join( [src_ticket_data['type'], src_ticket_data['component']] )
        }

        milestone = src_ticket_data['milestone']
        if milestone and milestone_map_id[milestone]:
            new_ticket_data["milestone_id"] = milestone_map_id[milestone]

        new_ticket = dest.create_issue(dest_project_id, new_ticket_data)
        new_ticket_id  = new_ticket["id"]
        # setting closed in create does not work -- bug in gitlab
        if is_closed: dest.close_issue(dest_project_id,new_ticket_id)

        # same for milestone
        if new_ticket_data.has_key("milestone_id"): dest.set_issue_milestone(dest_project_id,new_ticket_id,new_ticket_data["milestone_id"])


        changelog = source.ticket.changeLog(src_ticket_id)
        for change in changelog:
            change_type = change[2]
            print >>sys.stderr, "\nProcessing changelog: '%s'" % (change_type)
            if (change_type == "comment"):
                comment = fix_wiki_syntax( change[4])
                dest.comment_issue(dest_project_id,new_ticket_id,comment)



