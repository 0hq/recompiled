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
    print(request.args.get('id'))
    try:
        magic.Token.validate(request.args.get('id'))
        return 'true'
    except:
        return 'false'

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
@app.route('/deny-request', methods=['POST'])
def deny_request():
    secret_code = request.form.get('secret_code')
    email = request.form.get('writer_email')
    r = main_db.Writers.find_one({ "email": email, "secret_code": secret_code})
    if (r):
        main_db.Writers.update_one({'email': email },{'$set': {'expired': True}})
        deny_email(email, r["genesis_inviter"])
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'fail'})

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    print(request.form)
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
        r = main_db.Writers.find_one({ "email": account_email })
        if r:
            acceptance_email(account_email, r["subscribers"][0])
            transfer_five_dollars()
        else:
            return "No writer invite existed"

    if event_type == 'checkout.session.completed':
        # checkout_session = stripe.checkout.Session.retrieve(id)
        writer = x.metadata.writer
        requester = x.customer_details.email
        requester_data = x.customer_details
        print(x)
        if not writer:
            return "Misformed data"
        
        r = main_db.Writers.find_one({ "email": writer })
        if r:
            new_sub = {
                "name": requester_data.name,
                "email": requester,
                "subscriber_since": datetime.now().replace(microsecond=0),
                "customer_id": x.id,
                "transaction_id": x.payment_intent
            }
            main_db.Writers.update_one({'email': writer },{'$push': {'subscribers': new_sub}})
            send_new_sub_email(writer, requester)
        else:
            db_entry = {
                "email": writer,
                "description": x.metadata.desc,
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
            main_db.Writers.insert_one(db_entry)
            send_request_email(writer, requester)
        
        print('🔔 Payment succeeded!')

    return jsonify({'status': 'success'})

# sends email to writer asking for confirmation.
def send_request_email(writer, requester):
    print ("(send_request_email)", writer, requester)
    writer_content = f'''\
        Subject: Someone wants to pay you $5/month to write!

        We just got an email from you to dispatch at Recompiled but it didn't look right. Double check that you included your writer code (you can check on our website) or that you sent from the right email account.

        If this wasn't you, reply to this email and we'll make sure your account is secure.

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

def deny_email(writer, requester):
    print ("(acceptance_email)", writer, requester)
    writer_content = f'''\
        Subject: You've accepted the invitation to write each month.

        Thanks for accepting your invitation to write updates each month. As a reminder: You'll have to send an email to dispatch@recompiled.fyi any time each month to get paid out your 5$/subscriber/month. We're sending you $5 right now in advance of your first post, to prove we're not kidding. 

        For more info, please access the panel at recompiled.fyi to manage your account and see more details.

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

def acceptance_email(writer, requester):
    print ("(acceptance_email)", writer, requester)
    writer_content = f'''\
        Subject: You've accepted the invitation to write each month.

        Thanks for accepting your invitation to write updates each month. As a reminder: You'll have to send an email to dispatch@recompiled.fyi any time each month to get paid out your 5$/subscriber/month. We're sending you $5 right now in advance of your first post, to prove we're not kidding. 

        For more info, please access the panel at recompiled.fyi to manage your account and see more details.

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
