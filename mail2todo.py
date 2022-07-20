#!/opt/rh/rh-python38/root/usr/bin/python3.8

######################################################
# Name: mail2todo.py
#
# Version: 0.1
# Author : Frederic Descamps <lefred@lefred.be>
#
# Date   : 0.1  - 19 JUL 2022 | initial release
#
######################################################

import mysqlx
import imaplib
import email
import base64
import re
import time
import getopt
import configparser
import sys
from datetime import datetime

debug = False
config_file = None


def pdebug(msg=None):
    if debug and msg:
        print("DEBUG: {}".format(msg), flush=True)


try:
    arguments, values = getopt.getopt(sys.argv[1:], "hc:", ["help", "config="])
except:
    print("mail2todo.py -c <config_file>")
    sys.exit(2)

for curr_arg, curr_value in arguments:
    if curr_arg in ("-h", "--help"):
        print("mail2todo.py -c <config_file>")
    elif curr_arg in ("-c", "--config"):
        config_file = curr_value

if not config_file:
    print("ERROR: config file missing")
    sys.exit(2)

pdebug("Config file is {}".format(config_file))

config = configparser.ConfigParser()
config.read(config_file)
sections = config.sections()

# parsing the config file

db_host = config["MySQL"].get("host", "localhost")
db_port = int(config["MySQL"].get("port", 33060))
db_schema = config["MySQL"].get("db")
db_user = config["MySQL"].get("user")
db_password = config["MySQL"].get("password")
db_ssl = config["MySQL"].get("ssl-mode", "REQUIRED")
db_prefix = config["MySQL"].get("prefix")

imap_host = config["imap"].get("host", "localhost")
imap_port = int(config["imap"].get("port", 993))
imap_user = config["imap"].get("user")
imap_password = config["imap"].get("password")

debug = config["general"].get("debug")

# allowed Content-Transfert-Encoding type email
content_encoding = [
    {"name": "base64", "encoded": True},
    {"name": "7bit", "encoded": False},
    {"name": "quoted-printable", "encoded": False},
]


def connect_db():
    session = mysqlx.get_session(
        {
            "host": db_host,
            "port": db_port,
            "user": db_user,
            "password": db_password,
            "schema": db_schema,
            "ssl-mode": db_ssl,
        }
    )
    return session


def connect_mail():
    try:
        imap = imaplib.IMAP4_SSL(host=imap_host, port=imap_port)
        imap.login(imap_user, imap_password)
    except Exception as e:
        print("ErrorType : {}, Error : {}".format(type(e).__name__, e))
        return None

    return imap


session = connect_db()
imap = connect_mail()

while True:

    if not session:
        session = connect_db()
    if not imap:
        imap = connect_mail()

    # Get the amount of mail in INBOX
    resp_code, mail_count = imap.select(mailbox="INBOX", readonly=False)
    if int(mail_count[0]) > 0:
        pdebug("New message(s): {}".format(int(mail_count[0])))
        # as we have new email, we can then retrieve them
        resp_code, mails = imap.search(None, "ALL")
        pdebug("Mail IDs : {}\n".format(mails[0].decode().split()))
        for mail_id in mails[0].decode().split():
            note = ""
            body_note = ""
            todo_title = ""
            resp_code, mail_data = imap.fetch(mail_id, "(RFC822)")  ## Fetch mail data.
            message = email.message_from_bytes(
                mail_data[0][1]
            )  ## Construct Message from mail data
            # currently no need to verify the sender
            # but I plan to have a list of approved emails (maybe in db) to
            # avoid spam for example
            pdebug("From       : {}".format(message.get("From")))
            # the tile in the todolist table will be the subject
            todo_title = message.get("Subject")
            pdebug("Todo Title : {}".format(todo_title))
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    # body_lines = part.as_string().split("\n")
                    body_lines = part.as_string()
                    found_encoding = False
                    for encoding in content_encoding:
                        if (
                            body_lines.find(
                                "Content-Transfer-Encoding: {}\n\n".format(
                                    encoding["name"]
                                )
                            )
                            > 1
                        ):
                            if encoding["encoded"]:
                                body_encoded = body_lines[
                                    body_lines.find(
                                        "Content-Transfer-Encoding: {}\n\n".format(
                                            encoding["name"]
                                        )
                                    )
                                    + (29 + len(encoding["name"])) :
                                ]
                                body_note = base64.b64decode(
                                    body_encoded.encode("utf8")
                                ).decode("utf8")
                            else:
                                body_note = body_lines[
                                    body_lines.find(
                                        "Content-Transfer-Encoding: {}\n\n".format(
                                            encoding["name"]
                                        )
                                    )
                                    + (29 + len(encoding["name"])) :
                                ]
                            found_encoding = True
                            break
                    if not found_encoding:
                        pdebug("Discarted: {}".format(body_lines))
                        continue
                    # pdebug(body_note)

                    # Now we need to split the first line with the tags
                    # and the rest of the message
                    tags_line, note = body_note.split("\n", 1)
                    pdebug("tags_line = {}".format(tags_line))
                    if "@" not in tags_line:
                        tags_line = None
                        note = body_note
                    else:
                        tags_line = tags_line.replace("@", "")
                    pdebug("tags_line = {}".format(tags_line))
                    # pdebug("Note   : {}".format(note))
                    # find the first word in the tags list to be considered as the mtt_list
                    # to use, if not we go to back to Todo
                    mtt_list = "Todo"
                    if tags_line:
                        mtt_list_re = re.search("[A-Z]+(?:s+[A-Z]+)*", tags_line)
                        if mtt_list_re:
                           mtt_list = mtt_list_re[0]
                           tags_line = tags_line.replace(mtt_list, "")
                        tags_line = tags_line.strip()
                    pdebug("List   : {}".format(mtt_list))
                    pdebug("Tags   : {}".format(tags_line))
                    # find the list's id
                    query = "SELECT id FROM {}lists WHERE name LIKE '{}'".format(
                        db_prefix, mtt_list
                    )
                    result = session.sql(query).execute().fetch_one()
                    if result:
                        mtt_list_id = result[0]
                    else:
                        # get the next ow for the task
                        query = "SELECT MAX(ow) FROM {}lists".format(db_prefix)
                        next_ow = 0
                        result = session.sql(query).execute().fetch_one()
                        if result:
                            next_ow = result[0]
                        # we need to create a new list
                        query = """INSERT INTO {}lists (uuid, ow, name, taskview) VALUES
                                   (uuid(), {}, '{}', 1)""".format(
                            db_prefix, next_ow, mtt_list
                        )
                        result = session.sql(query).execute()
                        mtt_list_id = result.get_autoincrement_value()

                    pdebug("List ID : {}".format(mtt_list_id))
                    # find the tags id list
                    tags_id_list = []
                    if tags_line:
                        tags_id_name = tags_line.split()
                        for tag_name in tags_id_name:

                            tag_name = tag_name.strip()
                            query = "SELECT id FROM {}tags WHERE name LIKE '{}'".format(
                                db_prefix, tag_name
                            )
                            result = session.sql(query).execute().fetch_one()
                            if result:
                                tags_id_list.append(str(result[0]))
                            else:
                                query = (
                                    "INSERT INTO {}tags (name) VALUES ('{}')".format(
                                        db_prefix, tag_name
                                    )
                                )
                                result = session.sql(query).execute()
                                tags_id_list.append(str(result.get_autoincrement_value()))
                        pdebug("Tags ID: {}".format(tags_id_list))
                    else:
                        tags_id_name = ""
                    # get the next ow for the task
                    query = "SELECT MAX(ow) FROM {}todolist WHERE list_id={} AND compl=0".format(
                        db_prefix, mtt_list_id
                    )
                    next_ow = 0
                    result = session.sql(query).execute().fetch_one()
                    if result:
                        next_ow = result[0]

                    # insert now the todo
                    query = """INSERT INTO {}todolist (uuid, list_id, d_created, title, note, ow, tags_ids, tags)
                               VALUES (uuid(), {}, UNIX_TIMESTAMP(), "{}", ?, {}, "{}","{}")""".format(
                        db_prefix,
                        mtt_list_id,
                        todo_title,
                        next_ow,
                        ", ".join(tags_id_list),
                        ", ".join(tags_id_name),
                    )
                    pdebug(query)
                    result = session.sql(query).bind(note).execute()
                    task_id = result.get_autoincrement_value()
                    pdebug("Inserted Todo ID: {}".format(task_id))
                    # we now insert the links in mtt_tag2task
                    if tags_line:
                        for tags_id in tags_id_list:
                            query = "INSERT INTO {}tag2task VALUES ({}, {}, {})".format(
                                db_prefix, tags_id, task_id, mtt_list_id
                            )
                            pdebug(query)
                            result = session.sql(query).execute()

            # remove the mail from mail server
            imap.store(mail_id, "+FLAGS", "\\Deleted")

    else:
        pdebug("No new message")
    imap.expunge()
    time.sleep(120)

imap.close()
imap.logout()
