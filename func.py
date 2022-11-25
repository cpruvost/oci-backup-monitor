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

import oci
import base64

def create_log_global_variable(ctx):
    #Log Level Configuration
    try:
        cfg = ctx.Config()
        log_level = cfg["log-level"]
        print("log level: " + log_level)
    except Exception as ex:
        print('ERROR: Missing configuration log level', ex, flush=True)
        raise

    try:
        if log_level == '50':
            logging.getLogger("my-backup-logger").setLevel(logging.CRITICAL)
        elif log_level == '40':
            logging.getLogger("my-backup-logger").setLevel(logging.ERROR)
        elif log_level == '30':
            logging.getLogger("my-backup-logger").setLevel(logging.WARNING)
        elif log_level == '20':
            logging.getLogger("my-backup-logger").setLevel(logging.INFO)
        elif log_level == '10':
            logging.getLogger("my-backup-logger").setLevel(logging.DEBUG)
        else: 
            logging.getLogger("my-backup-logger").setLevel(logging.INFO)                
                
        global log
        log = logging.getLogger("my-backup-logger")

    except Exception as ex:
        print('ERROR: Problem with log level configuration', ex, flush=True)
        raise    

# Get SMTP password from OCI Vault secret
def get_smtp_pwd_text_secret(ctx):
    log.info("Get SMTP password from OCI Vault secret")
    try:
        cfg = ctx.Config()
        email_smtp_pwd_secret_id = cfg["email_smtp_pwd_secret_id"]
        log.debug("email_smtp_pwd_secret_id" + email_smtp_pwd_secret_id)
    except Exception as ex:
        log.error('Missing configuration for Vault SMTP Secrets')
        raise

    #decrypted_secret_content = ""
    signer = oci.auth.signers.get_resource_principals_signer()
    try:
        client = oci.secrets.SecretsClient({}, signer=signer)
        secret_content = client.get_secret_bundle(email_smtp_pwd_secret_id).data.secret_bundle_content.content.encode('utf-8')
        global decrypted_smtp_pwd_secret_content
        decrypted_smtp_pwd_secret_content = base64.b64decode(secret_content).decode("utf-8")
        #log.info("decrypted_smtp_pwd_secret_content : " + decrypted_smtp_pwd_secret_content)
    except Exception as ex:
        log.error(f"failed to retrieve the smtp secret content: {ex}")
        raise
    return {"secret content": decrypted_smtp_pwd_secret_content}

# Get Database password from OCI Vault secret
def get_db_pwd_text_secret(ctx):
    log.info("Get Database password from OCI Vault secret")
    try:
        cfg = ctx.Config()
        db_pwd_secret_id = cfg["db_pwd_secret_id"]
        log.debug("db_pwd_secret_id" + db_pwd_secret_id)
    except Exception as ex:
        log.error('Missing configuration for Vault Db Secret')
        raise

    #decrypted_secret_content = ""
    signer = oci.auth.signers.get_resource_principals_signer()
    try:
        client = oci.secrets.SecretsClient({}, signer=signer)
        secret_content = client.get_secret_bundle(db_pwd_secret_id).data.secret_bundle_content.content.encode('utf-8')
        global decrypted_db_pwd_secret_content
        decrypted_db_pwd_secret_content = base64.b64decode(secret_content).decode("utf-8")
        #log.info("decrypted_db_pwd_secret_content : " + decrypted_db_pwd_secret_content)
    except Exception as ex:
        log.error(f"failed to retrieve the db secret content: {ex}")
        raise
    return {"secret content": decrypted_db_pwd_secret_content}    

def handler(ctx, data: io.BytesIO=None):
    try:
        #Log Level Configuration
        create_log_global_variable(ctx)

        #get smtp pwd
        get_smtp_pwd_text_secret(ctx)
        
        #get db pwd
        get_db_pwd_text_secret(ctx)

        #Print Event Log
        body = json.loads(data.getvalue())
        eventtype = body["eventType"]
        log.info("event type: " + body["eventType"])
        log.info("compartment name: " + body["data"]["compartmentName"])
        log.debug("Full Cloud Event Json Data:")
        log.debug(json.dumps(body, indent=4))

        #Send Email
        send_email(ctx, eventtype)

        #Insert into ADW
        #Change quote by double quote to have a valid json
        valid_json = json.dumps(body)
        insert_status = soda_insert(ctx, valid_json)
        if "id" in insert_status["items"][0]:
            log.info("Successfully inserted document ID " + insert_status["items"][0]["id"])
        else:
            raise SystemExit("Error while inserting: " + insert_status)

    except (Exception) as ex:
        log.error(f"Exception in handler occurred: {ex}")
        raise

    return response.Response(
        ctx,
        response_data=json.dumps(body),
        headers={"Content-Type": "application/json"}
    )

def send_email(ctx, eventtype):
    log.info("Sending Email")
    smtp_username = smtp_password = smtp_host = ""
    smtp_port = 0
    sender_email = sender_name = recipient = subject = body = ""
    try:
        cfg = ctx.Config()
        smtp_username = cfg["smtp-username"]
        smtp_host = cfg["smtp-host"]
        smtp_port = cfg["smtp-port"]
    except Exception as ex:
        log.error(f"Missing configuration for SMTP: {ex}")
        raise

    #Update variables as you want or use new configuration variables
    try:
        #Update the sender_email with Approved Sender that you created for this demo.
        sender_email = "mybackup@example.com"
        sender_name = "Mr Backup"
        recipient = "cpruvost44@gmail.com"
        subject = f"Backup {eventtype}"
        body = "WRITE YOUR OWN MESSAGE"
    except Exception as ex:
        log.error(f"Missing configuration for Email: {ex}")
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
        #server.login(smtp_username, smtp_password)
        server.login(smtp_username, decrypted_smtp_pwd_secret_content)
        server.sendmail(sender_email, recipient, msg.as_string())
        server.close()
    except Exception as ex:
        log.error(f"Email Sending Failed: {ex}")
        raise
    else:
        log.info ("Email Successfully Sent!")

    return response.Response(
        ctx, 
        response_data="Email successfully sent!",
        headers={"Content-Type": "application/json"}
    )

def soda_insert(ctx, valid_json):
    log.info("Inserting Event in Autonomous Database")
    try:
        cfg = ctx.Config()
        ordsbaseurl = cfg["ords-base-url"]
        schema = cfg["db-schema"]
        dbuser = cfg["db-user"]
    except Exception as e:
        log.error('Missing Configuration for Database')
        raise

    auth=(dbuser, decrypted_db_pwd_secret_content)
    sodaurl = ordsbaseurl + schema + '/soda/latest/'
    collectionurl = sodaurl + "backup"
    headers = {'Content-Type': 'application/json'}
    
    log.debug(valid_json)
    r = requests.post(collectionurl, auth=auth, headers=headers, data=valid_json)
    r_json = {}
    try:
        r_json = json.loads(r.text)
    except ValueError as e:
        print(r.text, flush=True)
        raise
    return r_json