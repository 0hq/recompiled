#! /usr/bin/env python3.6

"""
server.py
Stripe Sample.
Python 3.6 or newer required.
"""
import json
import os
import email
import smtplib, ssl
import imaplib
import stripe
import smtplib
import random
import math
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from flask import Flask, jsonify, render_template, redirect, request, session, send_from_directory
from pymongo import MongoClient
load_dotenv(find_dotenv())

EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')
IMAP_SERVER = os.getenv('IMAP_SERVER')
SMTP_SERVER = os.getenv('SMTP_SERVER')
PORT = 465  # For SSL

from magic_admin import Magic
magic = Magic()

# pprint library is used to make the output look more pretty
from pprint import pprint
# # connect to MongoDB, change the << MONGODB URL >> to reflect your own connection string
url = os.getenv('MONGO_URL')
client = MongoClient("mongodb+srv://server:Pfi88XLO8TrqSgqY@cluster0.ztv48.mongodb.net/Main?retryWrites=true&w=majority")
# db = client["Writers"]
# Issue the serverStatus command and print the results
# serverStatusResult=db.command("serverStatus")
test = client.Main.Writers.find()
main_db = client.Main
wdb = main_db.Writers
# print(test)
for r in test:
    print(r)

# Setup Stripe python client library
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = os.getenv('STRIPE_API_VERSION', '2019-12-03')

static_dir = str(os.path.abspath(os.path.join(__file__ , "..", os.getenv("STATIC_DIR"))))
app = Flask(__name__, static_folder=static_dir,
            static_url_path="", template_folder=static_dir)

# Set the secret key to some random bytes. Keep this really secret!
# This enables Flask sessions.
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

@app.route('/register', methods=['GET'])
def get_register():
    return render_template('register.html')

@app.route('/login', methods=['GET'])
def get_login():
    return render_template('login.html')

@app.route('/requestThatNeedsAuth', methods=['GET'])
def requestThatNeedsAuth():
    id = request.args.get('id')
    print(id)
    try:
        magic.Token.validate(id)
        return 'true'
    except:
        return jsonify("Invalid token"), 401

@app.route('/get_user', methods=['GET'])
def get_user():
    id = request.args.get('id')
    print(id)
    try:
        magic.Token.validate(id)
        issuer = magic.Token.getIssuer(id)
    except:
        return jsonify("Invalid token"), 401

    user_subs = wdb.find(
            {"subscribers": {"$elemMatch": { "magic_id": issuer }}},  
            { "subscribers": 0 })
    return jsonify(user_subs)

@app.route('/cancel_sub', methods=['GET'])
def cancel_sub():
    id = request.args.get('id')
    writer = request.args.get('writer')
    print(id)
    try:
        magic.Token.validate(id)
        issuer = magic.Token.getIssuer(id)
        user_info = magic.User.get_metadata_by_issuer(issuer).data
    except:
        return jsonify("Invalid token"), 401

    wdb.update_one(
            {"email": writer },  
            { "$pull": {"subscribers": { "magic_id": issuer }} })
    cancel_email(writer, user_info["email"])
    # cancel user subscription
    return jsonify("success")

@app.route('/old_cancel_writer', methods=['GET'])
def old_cancel_writer():
    id = request.args.get('id')
    print(id)
    try:
        magic.Token.validate(id)
        issuer = magic.Token.getIssuer(id)
        user_info = magic.User.get_metadata_by_issuer(issuer).data
    except:
        return jsonify("Invalid token"), 401

    w = wdb.find_one_and_update({'email': user_info["email"] },{'$set': {'expired': True}})
    cancel_writer_email(writer, w["subscribers"])
    # cancel user subscriptions
    return jsonify("success")

# Fetch the Checkout Session to display the JSON result on the success page
@app.route('/cancel_writer', methods=['GET'])
def cancel_writer():
    secret_code = request.args.get('secret_code')
    email = request.args.get('writer_email')
    r = wdb.find_one({ "email": email, "secret_code": secret_code})
    if r:
        wdb.update_one({'email': email },{'$set': {'expired': True}})
        cancel_writer_email(writer, r["subscribers"])
        # cancel user subscriptions
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'fail'})

@app.route('/onboard-user', methods=['POST'])
def onboard_user():
    account = stripe.Account.create(type='express')
    # Store the account ID.
    session['account_id'] = account.id

    origin = request.headers['origin']
    account_link_url = _generate_account_link(account.id, origin)
    try:
        return jsonify({'url': account_link_url})
    except Exception as e:
        return jsonify(error=str(e)), 403

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
        return_url=f'{origin}/success.html',
    )
    return account_link.url


@app.route('/', methods=['GET'])
def get_example():
    return render_template('index.html')

@app.route('/get-writers', methods=['GET'])
def get_writers():
    ws = wdb.find({}, { "email": 1, "name": 1, "desc": 1, "subscribers": 1 })
    for w, i in enumerate(ws)
        w["subscribers"] = len(w["subscribers"])
        ws[i] = w
    return ws

@app.route('/config', methods=['GET'])
def get_publishable_key():
    return jsonify({
        'publishableKey': os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'basicPrice': "price_1Kx1ECEDdGyhVvwd5Q0BTcOX",
        'proPrice': "price_1Kx1ECEDdGyhVvwd5Q0BTcOX"
    })

# Fetch the Checkout Session to display the JSON result on the success page
@app.route('/checkout-session', methods=['GET'])
def get_checkout_session():
    id = request.args.get('sessionId')
    checkout_session = stripe.checkout.Session.retrieve(id)
    return jsonify(checkout_session)

# Fetch the Checkout Session to display the JSON result on the success page
@app.route('/request', methods=['GET'])
def deny_request():
    secret_code = request.args.get('secret_code')
    email = request.args.get('writer_email')
    return render_template('index.html') # request.html

# Fetch the Checkout Session to display the JSON result on the success page
@app.route('/deny-request', methods=['GET'])
def deny_request():
    secret_code = request.args.get('secret_code')
    email = request.args.get('writer_email')
    r = wdb.find_one({ "email": email, "secret_code": secret_code})
    if r:
        wdb.update_one({'email': email },{'$set': {'expired': True}})
        deny_email(email, r["genesis_inviter"])
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'fail'})


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    price = request.form.get('priceId')
    writer = request.form.get('writerEmail')
    desc = request.form.get('descText')
    print(price, writer, desc)
    domain_url = os.getenv('DOMAIN')

    try:
        # Create new Checkout Session for the order
        # Other optional params include:
        # [billing_address_collection] - to display billing address details on the page
        # [customer] - if you have an existing Stripe Customer ID
        # [customer_email] - lets you prefill the email input in the form
        # [automatic_tax] - to automatically calculate sales tax, VAT and GST in the checkout page
        # For full details see https://stripe.com/docs/api/checkout/sessions/create

        # ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param
        subscription_data = {
            'writer': writer,
            'desc': desc,
        }
        checkout_session = stripe.checkout.Session.create(
            success_url=domain_url + '/success.html?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain_url + '/canceled.html',
            mode='payment',
            # automatic_tax={'enabled': True},
            metadata=subscription_data,
            payment_intent_data={
                'metadata': subscription_data      
            },
            line_items=[{
                'name': writer,
                'amount': 51,
                'currency': 'usd',
                'quantity': 1
            }]
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify({'error': {'message': str(e)}}), 400

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


@app.route('/webhook', methods=['POST'])
def webhook_received():
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

    # fix this
    if event_type == 'account.session.completed':
        account_email = x.email
        r = wdb.find_one({ "email": account_email })
        if r:
            acceptance_email(account_email, r["subscribers"][0])
            transfer_five_dollars()
        else:
            return "No writer invite existed"

    if event_type == 'checkout.session.completed':
        # checkout_session = stripe.checkout.Session.retrieve(id)
        meta = x.metadata
        writer = x.metadata.writer
        requester = x.customer_details.email
        requester_data = x.customer_details
        secret_code = random.random() * 10 ** 8
        print(x)
        if not writer:
            return "Misformed data"
        
        r = wdb.find_one({ "email": writer })
        if r:
            new_sub = {
                "name": requester_data.name,
                "email": requester,
                "subscriber_since": datetime.now().replace(microsecond=0),
                "customer_id": x.id,
                "transaction_id": x.payment_intent
            }
            wdb.update_one({'email': writer },{'$push': {'subscribers': new_sub}})
            send_new_sub_email(writer, requester)
        else:
            db_entry = {
                "email": writer,
                "description": meta.desc,
                "genesis_inviter": requester,
                "start_date": datetime.now().replace(microsecond=0),
                "strikes":[],
                "accepted": false,
                "subscribers":[
                    {
                        "name": requester_data.name,
                        "email": requester,
                        "subscriber_since":datetime.now().replace(microsecond=0),
                        "customer_id": x.id,
                        "transaction_id": x.payment_intent
                    }
                ]
            }
            print(db_entry)
            wdb.insert_one(db_entry)
            send_request_email(writer, requester, meta.desc, secret_code)
        
        print('🔔 Payment succeeded!')

    return jsonify({'status': 'success'})

# sends email to writer asking for confirmation.
def send_request_email(writer, requester, desc, code):
    print ("(send_request_email)", writer, requester)
    writer_content = f'''\
        Subject: Someone wants to pay you $5/month to write!

        {requester} has requested you to start a monthly newsletter on specific topic. If you accept, you'll get $5/month per subscriber that signs up, all you have to do is send an email newsletter every month, covering "{desc}".

        If you're interested in learning more, head to https://recompiled.fyi/request?writer={writer}&code={code}

        If you're not interested, feel free to deny this request by clicking here: https://recompiled.fyi/deny-request?writer={writer}&code={code}

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

def transfer_five_dollars():
    # stripe send five dollars to the user
    print ("(transfer_five_dollars)")

def accept_email(writer, requester):
    print ("(acceptance_email)", writer, requester)
    writer_content = f'''\
        Subject: You've accepted the invitation to write each month.

        Thanks for accepting your invitation to write updates each month. As a reminder: You'll have to send an email to dispatch@recompiled.fyi any time each month to get paid out your 5$/subscriber/month. We're sending you $5 right now in advance of your first post, to prove we're not kidding. 

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
        - Will DePue
    '''
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

def send_email(receiver_email, content):
    with smtplib.SMTP_SSL(SMTP_SERVER, PORT, context=context) as server:
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, receiver_email, content)

if __name__== '__main__':
    app.run(port=4242)
