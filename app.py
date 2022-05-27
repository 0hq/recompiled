#! /usr/bin/env python3.6

"""
server.py
Will DePue
Python 3.6 or newer required.
"""
import json
import os
import email
import smtplib, ssl
import imaplib
from traceback import print_tb
import smtplib
import random
import math
from pprint import pprint
from xmlrpc.client import Boolean
from bson import json_util
from magic_admin import Magic
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv, find_dotenv
from flask import Flask, jsonify as j, render_template, redirect, request, session, send_from_directory
import stripe
from flask_cors import CORS



load_dotenv(find_dotenv())

EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')
IMAP_SERVER = os.getenv('IMAP_SERVER')
SMTP_SERVER = os.getenv('SMTP_SERVER')
PORT = 465  # For SSL

context = ssl.create_default_context()
magic = Magic()
url = os.getenv('MONGO_URL')
client = MongoClient("mongodb+srv://server:Pfi88XLO8TrqSgqY@cluster0.ztv48.mongodb.net/Main?retryWrites=true&w=majority")
main_db = client.Main
wdb = main_db.Writers
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = os.getenv('STRIPE_API_VERSION', '2019-12-03')
static_dir = str(os.path.abspath(os.path.join(__file__ , "..", os.getenv("STATIC_DIR"))))
app = Flask(__name__, static_folder=static_dir,
            static_url_path="", template_folder=static_dir)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
CORS(app)

def o(data):
    return json.loads(json_util.dumps(data))

def send_email(receiver_email, content):
    print(EMAIL, receiver_email, content)
    with smtplib.SMTP_SSL(SMTP_SERVER, PORT, context=context) as server:
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, receiver_email, content)

# ---------------- setup stuff above ----------

@app.route('/onboard-user', methods=['POST'])
def onboard_user():
    print(request.data)
    data = json.loads(request.data)
    print(data)
    secret_code = data.get('secret_code')
    email = data.get('writer_email')
    save = {'secret_code': secret_code, 'email': email}
    print(save)
    account = stripe.Account.create(
        type='express',
        metadata=save
    )
    print(account.metadata)
    # Store the account ID.
    session['account_id'] = account.id
    print(request.headers)
    origin = request.headers.get('origin')
    # print(origin, origin == '', Boolean(origin))
    if origin:
        account_link_url = _generate_account_link(account.id, origin)
        print(account_link_url)
        try:
            return j({'url': account_link_url})
        except Exception as e:
            return j(error=str(e)), 403
    return j({'status': "No origin url..."})

@app.route('/onboard-user/refresh', methods=['GET'])
def onboard_user_refresh():
    if 'account_id' not in session:
        return redirect('/')

    account_id = session['account_id']

    origin = ('https://' if request.is_secure else 'http://') + request.headers['host']
    account_link_url = _generate_account_link(account_id, origin)
    return redirect(account_link_url)

def _generate_account_link(account_id, origin):
    account_link = stripe.AccountLink.create(
        type='account_onboarding',
        account=account_id,
        refresh_url=f'{origin}/onboard-user/refresh',
        return_url=f'{origin}/success-register',
    )
    return account_link.url

@app.route('/', methods=['GET'])
def get_example():
    return render_template('index.html')

@app.route('/config', methods=['GET'])
def get_publishable_key():
    return j({
        'publishableKey': os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'ba,sicPrice': "price_1Kx1ECEDdGyhVvwd5Q0BTcOX",
        'proPrice': "price_1Kx1ECEDdGyhVvwd5Q0BTcOX"
    })

# Fetch the Checkout Session to display the JSON result on the success page
@app.route('/checkout-session', methods=['GET'])
def get_checkout_session():
    id = request.args.get('sessionId')
    checkout_session = stripe.checkout.Session.retrieve(id)
    return j(checkout_session)

@app.route('/customer-portal', methods=['POST'])
def customer_portal():
    # For demonstration purposes, we're using the Checkout session to retrieve the customer ID.
    # Typically this is stored alongside the authenticated user in your database.
    checkout_session_id = request.form.get('sessionId')
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    # This is the URL to which the customer will be redirected after they are
    # done managing their billing with the portal.
    return_url = os.getenv("DOMAIN")

    session = stripe.billing_portal.Session.create(
        customer=checkout_session.customer,
        return_url=return_url,
    )
    return redirect(session.url, code=303)

# ------------------------ stripe stuff above --------

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    writer = request.form.get('writerEmail')
    desc = request.form.get('descText')
    requestBool = request.form.get('requestBool')
    domain_url = os.getenv('DOMAIN')
    print(writer, desc, requestBool, domain_url)

    if not writer:
        return j({'misformed': [ writer, desc, requestBool, domain_url]})


    try:
        # Create new Checkout Session for the order
        # Other optional params include:
        # [billing_address_collection] - to display billing address details on the page
        # [customer] - if you have an existing Stripe Customer ID
        # [customer_email] - lets you prefill the email input in the form
        # [automatic_tax] - to automatically calculate sales tax, VAT and GST in the checkout page
        # For full details see https://stripe.com/docs/api/checkout/sessions/create

        # ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param
        meta = {
            'writer': writer,
            'desc': desc,
            'requestBool': requestBool == 'true'
        }
        now = datetime.now()
        trial = (now + timedelta(days=8))
        checkout_session = stripe.checkout.Session.create(
            success_url=domain_url + '/success-checkout',
            cancel_url=domain_url + '/failure',
            mode='subscription',
            # automatic_tax={'enabled': True},
            metadata=meta,
            subscription_data={
                'trial_end': trial
            },
            line_items=[{
                'price': "price_1L0gfqEDdGyhVvwdhITGKMN9",
                'quantity': 1
            }]
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return j({'error': {'message': str(e)}}), 400


@app.route('/webhook', methods=['POST'])
def webhook_received():
    # stripe listen --forward-to localhost:4242/webhook
    # You can use webhooks to receive information about asynchronous payment events.
    # For more about our webhook events check out https://stripe.com/docs/webhooks.
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    x = data['object']

    print('event ' + event_type)

    if event_type == 'capability.updated':
        if x["id"] == 'transfers':
            print(x['account'])
            acc = stripe.Account.retrieve(x['account'])
            print(acc.metadata)
            if acc.metadata.get('email') == None or acc.metadata.get('secret_code') == None:
                return "Metadata wrong"
            
            account_email = acc['metadata']['email']
            secret_code = acc['metadata']['secret_code']
            r = wdb.find_one({ "email": account_email, 'secret_code': secret_code, 'accepted': False, 'expired': False })
            if r:
                wdb.update_one({'email': account_email },{'$set': {'accepted': True, 'account_id': x['account'] }})
                accept_email(account_email, r["genesis_inviter"])
                stripe.Subscription.modify(r["subscribers"][0]["transaction_id"],
                    trial_end='now',
                )
            else:
                return "No writer invite existed"

    if event_type == 'checkout.session.completed':
        print(x.metadata)
        if not x.metadata.get('writer'):
            return "Metadata wrong"
        writer = x.metadata.writer
        desc = x.metadata.desc
        print(x.metadata.requestBool, type(x.metadata.requestBool), x.metadata.requestBool == "True", x.metadata.requestBool == True, x.metadata.requestBool == 'True')
        requestBool = x.metadata.requestBool == "True"
        requester = x.customer_details.email
        name = x.customer_details.name
        secret_code = str(int(random.random() * 10 ** 8))
        
        r = wdb.find_one({ "email": writer, 'accepted': True, 'expired': False })
        print(r, requestBool, Boolean(r), Boolean(requestBool))
        if r and not requestBool:
            new_sub = {
                "name": name,
                "email": requester,
                "subscriber_since": datetime.now().replace(microsecond=0),
                "customer_id": x.id,
                "transaction_id": x.subscription
            }
            stripe.Subscription.modify(x.subscription,
                    trial_end='now',
                )
            wdb.update_one({'email': writer },{'$push': {'subscribers': new_sub}})
            send_new_sub_emails(writer, requester)
        elif requestBool and not r:
            db_entry = {
                "name": "",
                "genesis_inviter": requester,
                "start_date": datetime.now().replace(microsecond=0),
                "strikes":[],
                "subscribers":[
                    {
                        "name": name,
                        "email": requester,
                        "subscriber_since": datetime.now().replace(microsecond=0),
                        "customer_id": x.id,
                        "transaction_id": x.subscription
                    }
                ],
                "email": writer,
                "secret_code": secret_code,
                "accepted": False,
                "expired": False,
                "description": desc,
                "last_send_date": datetime.now().replace(microsecond=0) - timedelta(weeks=52),
                "account_id": ""
            }
            print(db_entry)
            wdb.insert_one(db_entry)
            send_request_email(writer, requester, desc, secret_code)
        
        print('🔔 Payment succeeded!')

    return j({'status': True})


# ------------------------ internal stripe api stuff above

@app.route('/register', methods=['GET'])
def get_register():
    return render_template('register.html')

@app.route('/login', methods=['GET'])
def get_login():
    return render_template('login.html')

@app.route('/get-user', methods=['GET'])
def get_user():
    id = request.args.get('id')
    print(id)
    try:
        magic.Token.validate(id)
        issuer = magic.Token.get_issuer(id)
        user_info = magic.User.get_metadata_by_issuer(issuer).data
    except:
        return j("Invalid token"), 401

    user_subs = wdb.find(
            {"subscribers": {"$elemMatch": { "email": user_info["email"]}}},  
            { "subscribers": 0 })
    return j(o(user_subs))

@app.route('/get-writer-via-secret', methods=['GET'])
def get_writer_via_secret():
    secret_code = request.args.get('secret_code')
    email = request.args.get('writer_email')
    print(secret_code, email)
    r = wdb.find_one({ "email": email, "secret_code": secret_code, "expired": False, "accepted": False})
    if r:
        return j(o(r))
    else:
        return j("Invalid data"), 401
        

@app.route('/get-writer', methods=['GET'])
def get_writer():
    id = request.args.get('id')
    print(id)
    try:
        magic.Token.validate(id)
        issuer = magic.Token.get_issuer(id)
        user_info = magic.User.get_metadata_by_issuer(issuer).data
    except:
        return j("Invalid token"), 401

    writer = wdb.find_one({ "email": user_info["email"], 'accepted': True, 'expired': False })
    return j(o(writer))

@app.route('/cancel-sub', methods=['GET'])
def cancel_sub():
    id = request.args.get('id')
    writer = request.args.get('writer')
    print(id)
    try:
        magic.Token.validate(id)
        issuer = magic.Token.getIssuer(id)
        user_info = magic.User.get_metadata_by_issuer(issuer).data
    except:
        return j("Invalid token"), 401

    r = wdb.find_one({"email": writer, "subscribers": {"$elemMatch": { "email": user_info["email"]}}})
    print(r)
    sub_id = r["subscribers"]["transaction_id"]
    print(sub_id)
    wdb.update_one(
            {"email": writer },  
            { "$pull": {"subscribers": { "email": user_info["email"]}} })
    cancel_email(writer, user_info["email"])
    try:
        stripe.Subscription.delete(sub_id)
    except:
        print("Failed to cancel sub for", sub_id)
    return j("success")


# done, need to test with live stripe stuff
@app.route('/cancel-writer', methods=['GET'])
def cancel_writer():
    secret_code = request.args.get('secret_code')
    email = request.args.get('writer_email')
    print(secret_code, email)
    r = wdb.find_one({ "email": email, "secret_code": secret_code, "expired": False, "accepted": True})
    if r:
        wdb.update_one({'email': email },{'$set': {'expired': True}})
        cancel_writer_email(email, r["subscribers"])
        for s in r["subscribers"]:
            try:
                stripe.Subscription.delete(s["transaction_id"])
            except:
                print("Failed to cancel sub for", s["transaction_id"])
        return render_template('sucessfulrequest.html')
    else:
        return render_template('somethingwentwrong.html')

@app.route('/accept-request', methods=['GET'])
def request_test():
    return render_template('index.html') # request.html

# done
@app.route('/deny-request', methods=['GET'])
def deny_request():
    secret_code = request.args.get('secret_code')
    email = request.args.get('writer_email')
    print(secret_code, email)
    r = wdb.find_one({ "email": email, "secret_code": secret_code, "accepted": False, "expired": False})
    if r:
        wdb.update_one({'email': email },{'$set': {'expired': True}})
        deny_email(email, r["genesis_inviter"])
        for s in r["subscribers"]:
            try:
                stripe.Subscription.delete(s["transaction_id"])
            except:
                print("Failed to cancel sub for", s["transaction_id"])
        return render_template('sucessfulrequest.html')
    else:
        return render_template('somethingwentwrong.html')

# DONE
@app.route('/get-writers', methods=['GET'])
def get_writers():
    writers = wdb.find({"email" : { "$exists": True}, "accepted": True, "expired": False }, { "email": 1, "description": 1, "subscribers": 1 })
    print(writers)
    output = []
    for writer in writers:
        # print(writer)
        writer["subscribers"] = len(writer["subscribers"])
        output.append(writer)
    return j(o(output))



# ------------------------ main functions above ------------


# sends email to writer asking for confirmation.
def send_request_email(writer, requester, desc, code):
    print ("(send_request_email)", writer, requester)
    writer_content = f'''\
Subject: Someone wants to pay you $5/month to write!

{requester} has requested you to start a monthly newsletter on specific topic. If you accept, you'll get $5/month per subscriber that signs up, all you have to do is send an email newsletter every month, covering "{desc}".

If you're interested in learning more, head to https://recompiled.fyi/request?writer_email={writer}&secret_code={code}

If you're not interested, feel free to deny this request by clicking here: https://recompiled.fyi/deny-request?writer_email={writer}&secret_code={code}

Have a nice day!
- Will DePue
    '''
    requester_content = f'''\
Subject: Your request to {writer} has been sent.

This is an email confirming your request to {writer} - they'll have 7 days to accept before this subscription is canceled and you are refunded.

Have a nice day!
- Will DePue
    '''    
    send_email(writer, writer_content) 
    send_email(requester, requester_content) 

def accept_email(writer, requester):
    print ("(accept_email)", writer, requester)
    writer_content = f'''\
Subject: You've accepted the invitation to write each month.

Thanks for accepting your invitation to write updates each month. As a reminder: You'll have to send an email to dispatch@recompiled.fyi any time each month to get paid out your 5$/subscriber/month. We'll send you $5 at the end of the month (starting from 7 days after you were requested). 

It would be best to send your genesis update soon, as it's really helpful for people to get a hang of what you'll be writing about early on after they subscribed. You can do that by sending to dispatch@recompiled.fyi or follow the detailed instrucations on the site.

For more info, please access the panel at recompiled.fyi to manage your account and see more details. Be sure to remember to send your update this month!

Have a nice day!
- Will DePue
    '''
    requester_content = f'''\
Subject: Your request to {writer} has been accepted!

{writer} has accepted your request to write each month. You'll be supporting their work for $5 and you can unsubscribe at any time @ recompiled.fyi. Thank you so much!

Have a nice day :)
- Will DePue
    '''    
    send_email(writer, writer_content) 
    send_email(requester, requester_content) 

def deny_email(writer, requester):
    print ("(acceptance_email)", writer, requester)
    writer_content = f'''\
Subject: You've denied the invitation to write each month.

You've succesfully denied the request from {requester}, if this was an error be sure to reach out to them to create a new request.

Have a nice day!
- Will DePue
    '''
    requester_content = f'''\
Subject: Your request to {writer} has been denied :(

{writer} has denied your request to write each month. Feel free to reach out to them and talk, but you'll have to create another request in order to start again. You can do that at recompiled.fyi at any time.

Have a nice day :)
- Will DePue
    '''    
    send_email(writer, writer_content) 
    send_email(requester, requester_content) 
    
def cancel_email(writer, sub):
    print ("(send_new_sub_emails)", writer, sub)
    sub_content = f'''\
Subject: You just canceled your subscription to {writer}'s monthly letter.

Your cancelation has succeeded and you'll no longer receive monthly letters from {writer}. If this was a mistake, feel free to re-subscribe at recompiled.fyi.

Have a nice day!
- Will DePue
    '''
    writer_content = f'''\
Subject: You just lost a subscriber.

{sub} has canceled their subscription.

Have a nice day!
- Will DePue
    '''
    send_email(writer, writer_content) 
    send_email(sub, sub_content) 

def cancel_writer_email(writer, subs):
    inviter_content = f'''\
Subject: A subscription of yours has ended.

{writer} has canceled their monthly letter. This subscription has been permanently expired.

Have a nice day!
- Will DePue'''
    writer_content = f'''\
Subject: Your monthly letter has been removed.

You've successfully canceled your monthly letter. This subscription will be permanently expired. You can always restart this subscription by asking a subscriber to issue a new invite or by signing up again at recompiled.fyi.

Have a nice day!
- Will DePue
    '''
    send_email(writer, writer_content) 
    for s in subs:
        send_email(s["email"], inviter_content)
    cancel_vendor_account(writer)

def cancel_vendor_account(writer):
    return True
    # stripe cancel the account, skipping for now

def send_new_sub_emails(writer, sub):
    print ("(send_new_sub_emails)", writer, sub)
    sub_content = f'''\
Subject: You just subscribed to {writer}'s monthly letter.

Your payment has succeeded and you'll now receive monthly letters from {writer}. You're currently supporting their work for $5 and you can unsubscribe at any time @ recompiled.fyi.
Have a nice day!
- Will DePue
    '''
    writer_content = f'''\
Subject: You just got a new subscriber!

Someone just signed up for a $5/month subscription from an email @ {sub}. Congratulations, keep up the good work :)

Have a nice day!
- Will DePue
    '''
    send_email(writer, writer_content) 
    send_email(sub, sub_content) 


# --------------------------- email stuff above -------

if __name__== '__main__':
    app.run()
