#! /usr/bin/env python3.6

"""
server.py
Stripe Sample.
Python 3.6 or newer required.
"""
import json
import os

import stripe
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from flask import Flask, jsonify, render_template, redirect, request, session, send_from_directory
from pymongo import MongoClient

# pprint library is used to make the output look more pretty
from pprint import pprint
# # connect to MongoDB, change the << MONGODB URL >> to reflect your own connection string
url = os.getenv('MONGO_URL')
client = MongoClient("mongodb+srv://server:Pfi88XLO8TrqSgqY@cluster0.ztv48.mongodb.net/Main?retryWrites=true&w=majority"
)
# db = client["Writers"]
# Issue the serverStatus command and print the results
# serverStatusResult=db.command("serverStatus")
test = client.Main.Writers.find()
main_db = client.Main
# print(test)
for r in test:
    print(r)

# Setup Stripe python client library
load_dotenv(find_dotenv())
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
    data_object = data['object']

    print('event ' + event_type)

    if event_type == 'checkout.session.completed':
        # checkout_session = stripe.checkout.Session.retrieve(id)
        print(data, request_data)
        db_entry = {
            "email": data.writer,
            "genesis_inviter": data.customer_details.email,
            "start_date": datetime.now().replace(microsecond=0),
            "strikes":[],
            "subscribers":[
                {
                    "name":data.customer_details.name,
                    "email":data.customer_details.email,
                    "subscriber_since":datetime.now().replace(microsecond=0),
                    "customer_id":data.id,
                    "transaction_id": data.payment_intent
                }
            ]
        }
        print(db_entry)
        main_db.Writers.insert_one(new_db_entry)
        send_request_email()
        # sets cron job to refund and alert if not accepted in one week
        print('🔔 Payment succeeded!')

    return jsonify({'status': 'success'})

# sends email to writer asking for confirmation.
def send_request_email():
    print ("(send_request_email)")

if __name__== '__main__':
    app.run(port=4242)
