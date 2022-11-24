#
# oci-backup-monitor version 1.0.
#
# -----------------------------------------------------------
# demonstrates how to monitor backup events on OCI using Function and Autonomous Db
#
# (C) 2022 Christophe Pruvost, Nantes, France
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl.
# -----------------------------------------------------------

import io
import json

from fdk import response

import smtplib 
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import logging

def handler(ctx, data: io.BytesIO=None):
    try:
        cfg = ctx.Config()
        loglevel = cfg["log-level"]
        print("log level: " + loglevel)
    except Exception as ex:
        print('ERROR: Missing configuration log level', ex, flush=True)
        raise

    try:
        logging.basicConfig(level=40)
        log = logging.getLogger("my-backup-logger")
        log.info("Hello, world")
        print("effective log level: " + str(log.getEffectiveLevel))
        #Print Event Log
        body = json.loads(data.getvalue())
        eventtype = body["eventType"]
        print("event type: " + body["eventType"])
        print("compartment name: " + body["data"]["compartmentName"])
        print("Full Cloud Event Json Data:")
        print(json.dumps(body, indent=4), flush=True)

        #Send Email
        send_email(ctx, eventtype)

        #Insert into ADW
        print("INFO - inserting into ADW")
        valid_json = json.dumps(body)
        insert_status = soda_insert(ctx, valid_json)
        print(insert_status)
        if "id" in insert_status["items"][0]:
            print("INFO - Successfully inserted document ID " + insert_status["items"][0]["id"], flush=True)
        else:
            raise SystemExit("Error while inserting: " + insert_status)

    except (Exception) as ex:
        print('ERROR: Missing key in payload', ex, flush=True)
        raise

    return response.Response(
        ctx,
        response_data=json.dumps(body),
        headers={"Content-Type": "application/json"}
    )

def send_email(ctx, eventtype):
    smtp_username = smtp_password = smtp_host = ""
    smtp_port = 0
    sender_email = sender_name = recipient = subject = body = ""
    try:
        cfg = ctx.Config()
        smtp_username = cfg["smtp-username"]
        smtp_password = cfg["smtp-password"]
        smtp_host = cfg["smtp-host"]
        smtp_port = cfg["smtp-port"]
    except Exception as ex:
        print('ERROR: Missing configuration key', ex, flush=True)
        raise
    try:
        sender_email = "mybackup@example.com"
        sender_name = "Mr Backup"
        recipient = "cpruvost44@gmail.com"
        subject = f"Backup {eventtype}"
        body = "WRITE YOUR OWN MESSAGE"
    except Exception as ex:
        print('ERROR: Missing key in payload', ex, flush=True)
        raise
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email.utils.formataddr((sender_name, sender_email))
    msg['To'] = recipient
    msg.attach(MIMEText(body, 'plain'))

    try: 
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, recipient, msg.as_string())
        server.close()
    except Exception as ex:
        print("ERROR: ", ex, flush=True)
        raise
    else:
        print ("INFO: Email successfully sent!", flush=True)

    return response.Response(
        ctx, 
        response_data="Email successfully sent!",
        headers={"Content-Type": "application/json"}
    )

def soda_insert(ctx, valid_json):
    try:
        cfg = ctx.Config()
        ordsbaseurl = cfg["ords-base-url"]
        schema = cfg["db-schema"]
        dbuser = cfg["db-user"]
        dbpwd = cfg["dbpwd-cipher"]
    except Exception as e:
        print('Missing function parameters: ordsbaseurl, schema, dbuser, dbpwd', flush=True)
        raise

    auth=(dbuser, dbpwd)
    sodaurl = ordsbaseurl + schema + '/soda/latest/'
    collectionurl = sodaurl + "backup"
    headers = {'Content-Type': 'application/json'}
    
    print(valid_json)
    r = requests.post(collectionurl, auth=auth, headers=headers, data=valid_json)
    r_json = {}
    try:
        r_json = json.loads(r.text)
    except ValueError as e:
        print(r.text, flush=True)
        raise
    return r_json